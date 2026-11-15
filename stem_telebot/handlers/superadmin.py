from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ReplyKeyboardMarkup
from telegram.ext import ConversationHandler, ContextTypes
from ..core import stats_web
from ..core.database import ACTIVITY_LOG_PATH, db
from ..ui import keyboards, states, strings
import os
import psutil
import time
import logging
import asyncio
from ..core.security_utils import log_security_event

logger = logging.getLogger(__name__)


def _public_base_url():
    return (
        os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
        or os.getenv("WEBHOOK_URL", "").rstrip("/")
    )


def _actor(update: Update) -> str:
    user = update.effective_user
    if not user:
        return "unknown"
    return user.first_name or str(user.id)


async def _require_superadmin(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else 0
    if not db.is_superadmin(uid):
        log_security_event("AUTHZ_DENY", f"surface=superadmin uid={uid}")
        return False
    return True


async def _require_inventory(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else 0
    if not db.is_inventory_user(uid):
        log_security_event("AUTHZ_DENY", f"surface=inventory uid={uid}")
        return False
    return True


def get_user_lang(context: ContextTypes.DEFAULT_TYPE):
    return context.user_data.get('lang', strings.DEFAULT_LANG)

async def run_db_call(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)

def get_super_menu(lang='EN'):
    return ReplyKeyboardMarkup([
        [strings.get('BTN_SA_MAINTENANCE', lang), strings.get('BTN_SA_REFRESH', lang)],
        [strings.get('BTN_SA_ADMINS', lang), strings.get('BTN_SA_HEALTH', lang)],
        [strings.get('BTN_SA_INVENTORY', lang), strings.get('BTN_SA_LOGS', lang)],
        [strings.get('BTN_SA_EXIT', lang)]
    ], resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    is_sa = db.is_superadmin(user_id)
    logger.info(f"DEBUG: /superadmin attempt by {user_id}. Is SA? {is_sa}. SA List: {db.superadmin_ids}")
    
    if not is_sa: 
        return ConversationHandler.END
    
    # Refresh config in the background so the dashboard opens without blocking on Sheets I/O.
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, db.refresh_system_config)
    
    lang = get_user_lang(context)
    status = "ON" if db.maintenance_mode else "OFF"
    
    await update.message.reply_text(
        f"*Superadmin Dashboard*\n\nMaintenance Mode: {status}",
        parse_mode="Markdown",
        reply_markup=get_super_menu(lang)
    )
    return states.SUPER_MENU


async def refresh_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_superadmin(update):
        return ConversationHandler.END
    await run_db_call(db.refresh_system_config, force=True)
    lang = get_user_lang(context)
    await update.message.reply_text(strings.get('MSG_CONFIG_REFRESHED', lang), parse_mode="Markdown")
    return states.SUPER_MENU

async def check_health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_superadmin(update):
        return ConversationHandler.END
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    uptime = time.time() - psutil.boot_time()
    
    hours = int(uptime // 3600)
    mins = int((uptime % 3600) // 60)
    
    msg = (
        f"*System Health*\n\n"
        f"CPU: *{cpu}%*\n"
        f"RAM: *{ram}%*\n"
        f"Uptime: ~*{hours}h* *{mins}m*"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
    return states.SUPER_MENU

async def toggle_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_superadmin(update):
        return ConversationHandler.END
    new_state = not db.maintenance_mode
    if await run_db_call(db.set_maintenance, new_state):
        status = "ENABLED" if new_state else "DISABLED"
        await update.message.reply_text(f"Maintenance Mode: *{status}*", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Failed to update config.")
    return states.SUPER_MENU

async def view_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_superadmin(update):
        return ConversationHandler.END
    try:
        with open(ACTIVITY_LOG_PATH, "rb") as log_file:
            await update.message.reply_document(
                document=log_file,
                filename="activity.txt"
            )
    except FileNotFoundError:
        await update.message.reply_text("📂 Log file is empty or missing.")
    except Exception as e:
        logger.error(e)
        await update.message.reply_text("❌ Error reading logs.")
    return states.SUPER_MENU


def get_manage_admins_menu(lang='EN'):
    return ReplyKeyboardMarkup([
        [strings.get('BTN_SA_ADD_ADMIN', lang), strings.get('BTN_SA_ADD_LOGISTICS', lang)],
        [strings.get('BTN_SA_LIST_ADMIN', lang), strings.get('BTN_SA_DEL_ADMIN', lang)],
        [strings.get('BTN_BACK', lang)]
    ], resize_keyboard=True)


async def manage_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_superadmin(update):
        return ConversationHandler.END
    lang = get_user_lang(context)
    await update.message.reply_text(
        strings.get('BTN_SA_ADMINS', lang),
        reply_markup=get_manage_admins_menu(lang)
    )
    return states.SUPER_ADMIN_MANAGE


async def _resolve_account_label(bot, user_id, fallback="Unknown"):
    """Resolve a Telegram ID to @username (or full name) for display."""
    try:
        chat = await bot.get_chat(user_id)
    except Exception:
        return fallback
    username = getattr(chat, "username", None)
    if username:
        return f"@{username}"
    name = " ".join(
        part for part in (chat.first_name, chat.last_name) if part
    ).strip()
    return name or fallback


async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_superadmin(update):
        return ConversationHandler.END
    try:
        accounts = await run_db_call(db.list_sheet_accounts)
    except Exception as e:
        logger.error("List accounts error: %s", e)
        accounts = []

    if not accounts:
        await update.message.reply_text(
            "No secondary accounts found.",
            reply_markup=get_manage_admins_menu(get_user_lang(context)),
        )
        return states.SUPER_ADMIN_MANAGE

    lines = [f"SECONDARY ACCOUNTS ({len(accounts)})", ""]
    for account in accounts:
        label = account["name"] or "Unknown"
        if not label.startswith("@"):
            resolved = await _resolve_account_label(
                context.bot, account["id"], fallback=label
            )
            if resolved != label:
                label = resolved
                await run_db_call(db.update_admin_name, account["id"], resolved)
        lines.append(f"{account['id']} - {label} - {account['role']}")

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=get_manage_admins_menu(get_user_lang(context)),
    )
    return states.SUPER_ADMIN_MANAGE


async def _prompt_add_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    role = context.user_data.get("add_account_role", "Admin")
    action = (
        "give inventory access (logistics role)"
        if role == "Logistics"
        else "add as Admin"
    )
    await update.message.reply_text(
        f"Add account - step 1/2\n\nSend the Telegram ID to {action}.",
        reply_markup=keyboards.get_cancel_menu(lang)
    )
    return states.SUPER_ADD_ID


async def add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_superadmin(update):
        return ConversationHandler.END
    context.user_data["add_account_role"] = "Admin"
    return await _prompt_add_account(update, context)


async def add_logistics_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_superadmin(update):
        return ConversationHandler.END
    context.user_data["add_account_role"] = "Logistics"
    return await _prompt_add_account(update, context)


async def add_admin_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_superadmin(update):
        return ConversationHandler.END
    lang = get_user_lang(context)
    text = update.message.text.strip()
    role = context.user_data.get("add_account_role", "Admin")
    
    if not text.isdigit():
        await update.message.reply_text(strings.get('ERR_SA_INVALID_ID', lang), parse_mode="Markdown")
        return states.SUPER_ADD_ID
        
    user_id = int(text)
    
    if db.is_admin(user_id) or db.is_logistics(user_id):
        await update.message.reply_text(
            strings.get('ERR_SA_ALREADY_ADMIN', lang),
            parse_mode="Markdown",
            reply_markup=get_manage_admins_menu(lang)
        )
        return states.SUPER_ADMIN_MANAGE

    # Resolve a username/display name so the account is recognizable later.
    label = await _resolve_account_label(context.bot, user_id)
    context.user_data["add_account_pending"] = {
        "id": user_id,
        "label": label,
        "role": role,
    }
    await update.message.reply_text(
        "Add account - step 2/2\n\n"
        f"ID: {user_id}\n"
        f"Name: {label}\n"
        f"Role: {role}\n\n"
        "Save this account?",
        reply_markup=keyboards.get_account_confirm_menu(lang),
    )
    return states.SUPER_ACCOUNT_CONFIRM


async def add_account_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_superadmin(update):
        return ConversationHandler.END
    lang = get_user_lang(context)
    pending = context.user_data.pop("add_account_pending", None)
    if not pending:
        await update.message.reply_text(
            "Nothing to confirm.",
            reply_markup=get_manage_admins_menu(lang),
        )
        return states.SUPER_ADMIN_MANAGE

    user_id = pending["id"]
    label = pending["label"]
    role = pending["role"]
    context.user_data.pop("add_account_role", None)

    if db.is_admin(user_id) or db.is_logistics(user_id):
        await update.message.reply_text(
            strings.get('ERR_SA_ALREADY_ADMIN', lang),
            parse_mode="Markdown",
            reply_markup=get_manage_admins_menu(lang),
        )
        return states.SUPER_ADMIN_MANAGE

    if await run_db_call(
        db.add_admin, user_id, label, f"SA:{update.effective_user.id}", role
    ):
        added_msg = (
            strings.get('MSG_SA_LOGISTICS_ADDED', lang)
            if role == "Logistics"
            else strings.get('MSG_SA_ADDED', lang)
        )
        promoted_msg = (
            strings.get('MSG_SA_LOGISTICS_PROMOTED', lang)
            if role == "Logistics"
            else strings.get('MSG_SA_PROMOTED', lang)
        )
        await update.message.reply_text(
            added_msg, parse_mode="Markdown", reply_markup=get_manage_admins_menu(lang)
        )

        # Notify the new account holder.
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=promoted_msg,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Failed to notify new account {user_id}: {e}")

        db.log_action(
            update.effective_user.first_name,
            "ADD_LOGISTICS" if role == "Logistics" else "ADD_ADMIN",
            f"Granted {role} to {user_id} ({label})",
        )
        return states.SUPER_ADMIN_MANAGE

    await update.message.reply_text(
        "❌ DB Error", reply_markup=get_manage_admins_menu(lang)
    )
    return states.SUPER_ADMIN_MANAGE


async def account_confirm_retry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    if not context.user_data.get("add_account_pending"):
        return await manage_admins(update, context)
    await update.message.reply_text(
        "Tap Confirm to save or Cancel to discard.",
        reply_markup=keyboards.get_account_confirm_menu(lang),
    )
    return states.SUPER_ACCOUNT_CONFIRM

async def del_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_superadmin(update):
        return ConversationHandler.END
    lang = get_user_lang(context)
    await update.message.reply_text(
        strings.get('PROMPT_SA_DEL', lang),
        parse_mode="Markdown",
        reply_markup=keyboards.get_cancel_menu(lang)
    )
    return states.SUPER_DEL_ID

async def del_admin_perform(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_superadmin(update):
        return ConversationHandler.END
    lang = get_user_lang(context)
    text = update.message.text.strip()
    
    if not text.isdigit():
        await update.message.reply_text(strings.get('ERR_SA_INVALID_ID', lang), parse_mode="Markdown")
        return states.SUPER_DEL_ID
        
    user_id = int(text)
    if await run_db_call(db.remove_admin, user_id):
        db.log_action(update.effective_user.first_name, "REMOVE_ADMIN", f"Demoted User {user_id}")
        await update.message.reply_text(strings.get('MSG_SA_DELETED', lang), parse_mode="Markdown", reply_markup=get_manage_admins_menu(lang))
    else:
        await update.message.reply_text("❌ Not found or Error", reply_markup=get_manage_admins_menu(lang))
        
    return states.SUPER_ADMIN_MANAGE

async def back_to_manage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("add_account_pending", None)
    context.user_data.pop("add_account_role", None)
    lang = get_user_lang(context)
    await update.message.reply_text(
        strings.get('ERR_CANCEL', lang),
        reply_markup=get_manage_admins_menu(lang)
    )
    return states.SUPER_ADMIN_MANAGE

async def back_to_super(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    await update.message.reply_text(
        "🔙 Superadmin Dashboard",
        reply_markup=get_super_menu(lang)
    )
    return states.SUPER_MENU


def _is_low_stock(item):
    qty = int(item.get("qty", 0))
    min_qty = int(item.get("min_qty", 0))
    return qty <= 0 or (min_qty > 0 and qty <= min_qty)


async def inventory_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_inventory(update):
        return ConversationHandler.END
    lang = get_user_lang(context)
    await update.message.reply_text(
        "*Inventory*\nChoose an action:",
        parse_mode="Markdown",
        reply_markup=keyboards.get_super_inventory_menu(lang),
    )
    return states.SUPER_INVENTORY_MENU


async def inventory_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_inventory(update):
        await update.message.reply_text(
            "Access denied. Inventory is for superadmins and the logistics role."
        )
        return ConversationHandler.END
    context.user_data.pop("inv_flow", None)
    return await inventory_menu(update, context)


async def inventory_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("inv_flow", None)
    lang = get_user_lang(context)
    uid = update.effective_user.id if update.effective_user else 0
    if db.is_superadmin(uid):
        await update.message.reply_text(
            "🔙 Superadmin Dashboard",
            reply_markup=get_super_menu(lang)
        )
        return states.SUPER_MENU
    await update.message.reply_text(
        "Back to main menu.",
        reply_markup=keyboards.get_main_menu(lang)
    )
    return ConversationHandler.END


async def inventory_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_inventory(update):
        return ConversationHandler.END
    lang = get_user_lang(context)
    try:
        items = await run_db_call(db.get_inventory_items)
    except Exception as e:
        logger.error("Inventory list error: %s", e)
        await update.message.reply_text(
            "❌ Inventory unavailable.",
            reply_markup=keyboards.get_super_inventory_menu(lang),
        )
        return states.SUPER_INVENTORY_MENU

    if not items:
        await update.message.reply_text(
            "No inventory items yet. Use *Add Item* to start.",
            parse_mode="Markdown",
            reply_markup=keyboards.get_super_inventory_menu(lang),
        )
        return states.SUPER_INVENTORY_MENU

    low_count = sum(1 for item in items if _is_low_stock(item))
    lines = ["STOCK LEVELS", f"{len(items)} item(s) | {low_count} low/out", ""]
    for item in items[:60]:
        flag = " [LOW]" if _is_low_stock(item) else ""
        unit = f" {item['unit']}" if item["unit"] else ""
        lines.append(f"{item['id']}  {item['name']} - {item['qty']}{unit}{flag}")
    if len(items) > 60:
        lines.append(f"...and {len(items) - 60} more")

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=keyboards.get_super_inventory_menu(lang),
    )
    return states.SUPER_INVENTORY_MENU


INVENTORY_ADD_FIELDS = ("name", "category", "qty", "unit", "location", "min_qty")

INVENTORY_ADD_PROMPTS = {
    "name": "What is the item name?",
    "category": "What category is it? (send - to skip)",
    "qty": "How many do you have right now? (whole number)",
    "unit": "What unit? e.g. pcs, ream (send - to skip)",
    "location": "Where is it stored? (send - to skip)",
    "min_qty": "Minimum stock level before warning? (send 0 to disable)",
}

INVENTORY_ADJUST_STEPS = ("item_id", "direction", "qty", "reason")


async def _send_inventory_prompt(update, context, text, markup=None):
    await update.message.reply_text(
        text,
        reply_markup=markup or keyboards.get_cancel_menu(get_user_lang(context)),
    )


async def _ask_add_step(update, context, flow):
    field = INVENTORY_ADD_FIELDS[flow["step"]]
    total = len(INVENTORY_ADD_FIELDS)
    text = (
        f"Add new item - step {flow['step'] + 1}/{total}\n\n"
        f"{INVENTORY_ADD_PROMPTS[field]}"
    )
    await _send_inventory_prompt(update, context, text)


async def _ask_adjust_step(update, context, flow):
    step = INVENTORY_ADJUST_STEPS[flow["step"]]
    lang = get_user_lang(context)
    if step == "item_id":
        text = (
            "Update stock - step 1/4\n\n"
            "Send the Item ID you want to change (e.g. INV-001)."
        )
        markup = keyboards.get_cancel_menu(lang)
    elif step == "direction":
        text = "Update stock - step 2/4\n\nAre you adding stock or taking it out?"
        markup = keyboards.get_inventory_direction_menu(lang)
    elif step == "qty":
        text = "Update stock - step 3/4\n\nHow many units?"
        markup = keyboards.get_cancel_menu(lang)
    else:
        text = "Update stock - step 4/4\n\nWhat is the reason? (send - for manual update)"
        markup = keyboards.get_cancel_menu(lang)
    await _send_inventory_prompt(update, context, text, markup)


async def inventory_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_inventory(update):
        return ConversationHandler.END
    flow = {"mode": "add", "step": 0, "data": {}}
    context.user_data["inv_flow"] = flow
    await _ask_add_step(update, context, flow)
    return states.SUPER_INVENTORY_INPUT


async def inventory_adjust_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_inventory(update):
        return ConversationHandler.END
    lang = get_user_lang(context)
    try:
        items = await run_db_call(db.get_inventory_items)
    except Exception as e:
        logger.error("Inventory adjust list error: %s", e)
        items = []

    if not items:
        await update.message.reply_text(
            "No inventory items yet. Add one first.",
            reply_markup=keyboards.get_super_inventory_menu(lang),
        )
        return states.SUPER_INVENTORY_MENU

    lines = ["Update stock - step 1/4", "", "Which item?"]
    for item in items[:20]:
        unit = f" {item['unit']}" if item["unit"] else ""
        lines.append(f"{item['id']} - {item['name']} ({item['qty']}{unit})")
    if len(items) > 20:
        lines.append(f"...and {len(items) - 20} more")
    lines.extend(["", "Send the Item ID (e.g. INV-001)."])

    context.user_data["inv_flow"] = {"mode": "adjust", "step": 0, "data": {}}
    await update.message.reply_text(
        "\n".join(lines), reply_markup=keyboards.get_cancel_menu(lang)
    )
    return states.SUPER_INVENTORY_INPUT


async def inventory_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("inv_flow", None)
    return await inventory_menu(update, context)


async def _inventory_add_input(update, context, flow):
    field = INVENTORY_ADD_FIELDS[flow["step"]]
    text = (update.message.text or "").strip()

    if field in ("qty", "min_qty"):
        if text in ("", "-"):
            text = "0"
        try:
            value = int(text)
        except ValueError:
            await _send_inventory_prompt(
                update,
                context,
                f"❌ Please send a whole number.\n\n{INVENTORY_ADD_PROMPTS[field]}",
            )
            return states.SUPER_INVENTORY_INPUT
        if value < 0:
            await _send_inventory_prompt(
                update,
                context,
                f"❌ Number cannot be negative.\n\n{INVENTORY_ADD_PROMPTS[field]}",
            )
            return states.SUPER_INVENTORY_INPUT
    else:
        value = "" if text == "-" else text
        if field == "name" and not value:
            await _send_inventory_prompt(
                update,
                context,
                f"❌ Item name cannot be empty.\n\n{INVENTORY_ADD_PROMPTS[field]}",
            )
            return states.SUPER_INVENTORY_INPUT

    flow["data"][field] = value
    flow["step"] += 1

    if flow["step"] < len(INVENTORY_ADD_FIELDS):
        await _ask_add_step(update, context, flow)
        return states.SUPER_INVENTORY_INPUT

    data = flow["data"]
    context.user_data.pop("inv_flow", None)
    result = await run_db_call(
        db.add_inventory_item,
        data["name"],
        data["category"],
        data["qty"],
        data["unit"],
        data["location"],
        data["min_qty"],
        _actor(update),
    )
    if not result.get("ok"):
        await update.message.reply_text(
            f"❌ Failed to add item: {result.get('error')}",
            reply_markup=keyboards.get_super_inventory_menu(get_user_lang(context)),
        )
        return states.SUPER_INVENTORY_MENU

    db.log_action(
        _actor(update),
        "INVENTORY_ADD",
        f"{result['id']} {data['name']} qty={data['qty']}",
    )
    unit = f" {data['unit']}" if data["unit"] else ""
    await update.message.reply_text(
        f"✅ Added {result['id']} - {data['name']} ({data['qty']}{unit}).",
        reply_markup=keyboards.get_super_inventory_menu(get_user_lang(context)),
    )
    return states.SUPER_INVENTORY_MENU


async def _inventory_adjust_input(update, context, flow):
    lang = get_user_lang(context)
    step = INVENTORY_ADJUST_STEPS[flow["step"]]
    text = (update.message.text or "").strip()

    if step == "item_id":
        if not text:
            await _send_inventory_prompt(update, context, "❌ Send the Item ID, e.g. INV-001.")
            return states.SUPER_INVENTORY_INPUT
        flow["data"]["item_id"] = text.upper()
    elif step == "direction":
        lowered = text.lower()
        if "in" in lowered or "+" in lowered:
            flow["data"]["direction"] = 1
        elif "out" in lowered or "-" in lowered:
            flow["data"]["direction"] = -1
        else:
            await _send_inventory_prompt(
                update,
                context,
                "❌ Tap Stock In (+) or Stock Out (-).",
                keyboards.get_inventory_direction_menu(lang),
            )
            return states.SUPER_INVENTORY_INPUT
    elif step == "qty":
        try:
            qty = int(text)
        except ValueError:
            await _send_inventory_prompt(update, context, "❌ Please send a whole number.")
            return states.SUPER_INVENTORY_INPUT
        if qty <= 0:
            await _send_inventory_prompt(update, context, "❌ Quantity must be more than zero.")
            return states.SUPER_INVENTORY_INPUT
        flow["data"]["qty"] = qty
    else:
        flow["data"]["reason"] = "Manual update" if text in ("", "-") else text

    flow["step"] += 1
    if flow["step"] < len(INVENTORY_ADJUST_STEPS):
        await _ask_adjust_step(update, context, flow)
        return states.SUPER_INVENTORY_INPUT

    data = flow["data"]
    context.user_data.pop("inv_flow", None)
    delta = data["qty"] * data["direction"]
    result = await run_db_call(
        db.adjust_inventory, data["item_id"], delta, data["reason"], _actor(update)
    )
    if not result.get("ok"):
        error = result.get("error")
        if error == "not_found":
            message = "❌ Item ID not found. Use List Stock to see IDs."
        elif error == "insufficient":
            message = f"❌ Not enough stock. Current: {result.get('current')}."
        else:
            message = f"❌ Failed: {error}"
        await update.message.reply_text(
            message, reply_markup=keyboards.get_super_inventory_menu(lang)
        )
        return states.SUPER_INVENTORY_MENU

    db.log_action(
        _actor(update),
        "INVENTORY_ADJUST",
        f"{result['id']} {delta:+d} -> {result['new_qty']} ({data['reason']})",
    )
    direction = "in" if delta > 0 else "out"
    await update.message.reply_text(
        f"✅ {result['id']} {result['name']}: "
        f"{result['current']} -> {result['new_qty']} ({direction} {data['qty']}, {data['reason']})",
        reply_markup=keyboards.get_super_inventory_menu(lang),
    )
    return states.SUPER_INVENTORY_MENU


async def inventory_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_inventory(update):
        return ConversationHandler.END
    flow = context.user_data.get("inv_flow")
    if not flow:
        return await inventory_menu(update, context)
    if flow.get("mode") == "adjust":
        return await _inventory_adjust_input(update, context, flow)
    return await _inventory_add_input(update, context, flow)


async def inventory_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_inventory(update):
        return ConversationHandler.END
    lang = get_user_lang(context)
    base_url = _public_base_url()
    if not base_url:
        await update.message.reply_text(
            "❌ Set PUBLIC_BASE_URL or WEBHOOK_URL to share the dashboard.",
            reply_markup=keyboards.get_super_inventory_menu(lang),
        )
        return states.SUPER_INVENTORY_MENU

    url = f"{base_url}/inventory/{stats_web.create_inventory_token(ttl_seconds=7 * 24 * 3600)}"
    await update.message.reply_text(
        "*Inventory Dashboard*\n"
        "_Read-only link. Share it with the team; it expires in 7 days._",
        parse_mode="Markdown",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Open Dashboard", url=url)]]
        ),
    )
    return states.SUPER_INVENTORY_MENU


async def exit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    await update.message.reply_text("Superadmin closed.", reply_markup=keyboards.get_main_menu(lang))
    return ConversationHandler.END
