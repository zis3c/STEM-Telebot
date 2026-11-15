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
    lang = get_user_lang(context)
    try:
        accounts = await run_db_call(db.list_sheet_accounts)
    except Exception as e:
        logger.error("List accounts error: %s", e)
        accounts = []

    if not accounts:
        await update.message.reply_text(
            strings.get('MSG_SA_LIST_EMPTY', lang),
            reply_markup=get_manage_admins_menu(lang),
        )
        return states.SUPER_ADMIN_MANAGE

    lines = [strings.get('MSG_SA_LIST_TITLE', lang).format(count=len(accounts))]
    for account in accounts:
        label = account["name"] or "Unknown"
        if not label.startswith("@"):
            resolved = await _resolve_account_label(
                context.bot, account["id"], fallback=label
            )
            if resolved != label:
                label = resolved
                await run_db_call(db.update_admin_name, account["id"], resolved)
        role_key = (
            'ROLE_LOGISTICS'
            if account["role"].strip().lower().startswith("logist")
            else 'ROLE_ADMIN'
        )
        lines.append(
            strings.get('MSG_SA_LIST_LINE', lang).format(
                id=account["id"],
                name=strings.escape_md(label),
                role=strings.get(role_key, lang),
            )
        )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=get_manage_admins_menu(lang),
    )
    return states.SUPER_ADMIN_MANAGE


async def _prompt_add_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    role = context.user_data.get("add_account_role", "Admin")
    question_key = 'PROMPT_SA_ADD_LOGISTICS' if role == "Logistics" else 'PROMPT_SA_ADD'
    await update.message.reply_text(
        strings.get('PROMPT_SA_ACCOUNT_STEP', lang).format(
            question=strings.get(question_key, lang)
        ),
        parse_mode="Markdown",
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
            strings.get('ERR_SA_ALREADY_ACCOUNT', lang),
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
    role_key = 'ROLE_LOGISTICS' if role == "Logistics" else 'ROLE_ADMIN'
    await update.message.reply_text(
        strings.get('PROMPT_SA_ACCOUNT_CONFIRM', lang).format(
            id=user_id,
            name=strings.escape_md(label),
            role=strings.get(role_key, lang),
        ),
        parse_mode="Markdown",
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
            strings.get('MSG_SA_ACCOUNT_PENDING_NONE', lang),
            parse_mode="Markdown",
            reply_markup=get_manage_admins_menu(lang),
        )
        return states.SUPER_ADMIN_MANAGE

    user_id = pending["id"]
    label = pending["label"]
    role = pending["role"]
    context.user_data.pop("add_account_role", None)

    if db.is_admin(user_id) or db.is_logistics(user_id):
        await update.message.reply_text(
            strings.get('ERR_SA_ALREADY_ACCOUNT', lang),
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
        strings.get('ERR_SA_ACCOUNT_DB', lang),
        parse_mode="Markdown",
        reply_markup=get_manage_admins_menu(lang),
    )
    return states.SUPER_ADMIN_MANAGE


async def account_confirm_retry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    if not context.user_data.get("add_account_pending"):
        return await manage_admins(update, context)
    await update.message.reply_text(
        strings.get('MSG_SA_ACCOUNT_CONFIRM_HINT', lang),
        parse_mode="Markdown",
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
        db.log_action(update.effective_user.first_name, "REMOVE_ADMIN", f"Removed account {user_id}")
        await update.message.reply_text(
            strings.get('MSG_SA_ACCOUNT_DELETED', lang),
            parse_mode="Markdown",
            reply_markup=get_manage_admins_menu(lang),
        )
    else:
        await update.message.reply_text(
            strings.get('ERR_SA_ACCOUNT_NOT_FOUND', lang),
            parse_mode="Markdown",
            reply_markup=get_manage_admins_menu(lang),
        )
        
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
        strings.get('INV_MENU', lang),
        parse_mode="Markdown",
        reply_markup=keyboards.get_super_inventory_menu(lang),
    )
    return states.SUPER_INVENTORY_MENU


async def inventory_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_inventory(update):
        await update.message.reply_text(
            strings.get('INV_ACCESS_DENIED', get_user_lang(context)),
            parse_mode="Markdown",
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
        strings.get('INV_EXIT', lang),
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
            strings.get('INV_ERR_GENERIC', lang).format(error="list_failed"),
            parse_mode="Markdown",
            reply_markup=keyboards.get_super_inventory_menu(lang),
        )
        return states.SUPER_INVENTORY_MENU

    if not items:
        await update.message.reply_text(
            strings.get('INV_EMPTY', lang),
            parse_mode="Markdown",
            reply_markup=keyboards.get_super_inventory_menu(lang),
        )
        return states.SUPER_INVENTORY_MENU

    low_count = sum(1 for item in items if _is_low_stock(item))
    lines = [
        strings.get('INV_LIST_TITLE', lang).format(
            count=len(items), low=low_count
        )
    ]
    for item in items[:60]:
        if item["qty"] <= 0:
            flag = " ⛔"
        elif _is_low_stock(item):
            flag = " ⚠️"
        else:
            flag = ""
        unit = f" {item['unit']}" if item["unit"] else ""
        lines.append(
            strings.get('INV_LIST_LINE', lang).format(
                id=strings.escape_md(item["id"]),
                name=strings.escape_md(item["name"]),
                qty=item["qty"],
                unit=strings.escape_md(unit),
                flag=flag,
            )
        )
    if len(items) > 60:
        lines.append(
            strings.get('INV_LIST_MORE', lang).format(count=len(items) - 60)
        )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=keyboards.get_super_inventory_menu(lang),
    )
    return states.SUPER_INVENTORY_MENU


INVENTORY_ADD_FIELDS = ("name", "category", "qty", "unit", "location", "min_qty")

INVENTORY_ADD_LABELS = {
    "name": "INV_LABEL_NAME",
    "category": "INV_LABEL_CATEGORY",
    "qty": "INV_LABEL_QTY",
    "unit": "INV_LABEL_UNIT",
    "location": "INV_LABEL_LOCATION",
    "min_qty": "INV_LABEL_MIN",
}

INVENTORY_ADD_QUESTIONS = {
    "name": "INV_Q_NAME",
    "category": "INV_Q_CATEGORY",
    "qty": "INV_Q_QTY",
    "unit": "INV_Q_UNIT",
    "location": "INV_Q_LOCATION",
    "min_qty": "INV_Q_MIN",
}

INVENTORY_ADJUST_STEPS = ("item_id", "direction", "qty", "reason")

INVENTORY_ADJUST_LABELS = {
    "item_id": "INV_LABEL_ITEM",
    "direction": "INV_LABEL_DIRECTION",
    "qty": "INV_LABEL_QTY",
    "reason": "INV_LABEL_REASON",
}

INVENTORY_ADJUST_QUESTIONS = {
    "item_id": "INV_Q_ITEM",
    "direction": "INV_Q_DIRECTION",
    "qty": "INV_Q_ADJUST_QTY",
    "reason": "INV_Q_REASON",
}


async def _send_inventory_prompt(update, context, text, markup=None):
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=markup or keyboards.get_cancel_menu(get_user_lang(context)),
    )


async def _ask_add_step(update, context, flow):
    lang = get_user_lang(context)
    field = INVENTORY_ADD_FIELDS[flow["step"]]
    text = strings.get('INV_ADD_STEP', lang).format(
        step=flow["step"] + 1,
        total=len(INVENTORY_ADD_FIELDS),
        label=strings.get(INVENTORY_ADD_LABELS[field], lang),
        question=strings.get(INVENTORY_ADD_QUESTIONS[field], lang),
    )
    await _send_inventory_prompt(update, context, text)


async def _ask_adjust_step(update, context, flow):
    lang = get_user_lang(context)
    step = INVENTORY_ADJUST_STEPS[flow["step"]]
    text = strings.get('INV_UPDATE_STEP', lang).format(
        step=flow["step"] + 1,
        total=len(INVENTORY_ADJUST_STEPS),
        label=strings.get(INVENTORY_ADJUST_LABELS[step], lang),
        question=strings.get(INVENTORY_ADJUST_QUESTIONS[step], lang),
    )
    markup = (
        keyboards.get_inventory_direction_menu(lang)
        if step == "direction"
        else keyboards.get_cancel_menu(lang)
    )
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
            strings.get('INV_EMPTY_ADJUST', lang),
            parse_mode="Markdown",
            reply_markup=keyboards.get_super_inventory_menu(lang),
        )
        return states.SUPER_INVENTORY_MENU

    lines = [
        strings.get('INV_UPDATE_HEADER', lang).format(
            step=1,
            total=len(INVENTORY_ADJUST_STEPS),
            label=strings.get(INVENTORY_ADJUST_LABELS["item_id"], lang),
        ),
        "",
    ]
    for item in items[:20]:
        if item["qty"] <= 0:
            flag = " ⛔"
        elif _is_low_stock(item):
            flag = " ⚠️"
        else:
            flag = ""
        unit = f" {item['unit']}" if item["unit"] else ""
        lines.append(
            strings.get('INV_LIST_LINE', lang).format(
                id=strings.escape_md(item["id"]),
                name=strings.escape_md(item["name"]),
                qty=item["qty"],
                unit=strings.escape_md(unit),
                flag=flag,
            )
        )
    if len(items) > 20:
        lines.append(
            strings.get('INV_LIST_MORE', lang).format(count=len(items) - 20)
        )
    lines.extend(["", strings.get('INV_Q_ITEM', lang)])

    context.user_data["inv_flow"] = {"mode": "adjust", "step": 0, "data": {}}
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=keyboards.get_cancel_menu(lang),
    )
    return states.SUPER_INVENTORY_INPUT


async def inventory_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("inv_flow", None)
    return await inventory_menu(update, context)


async def _inventory_add_input(update, context, flow):
    lang = get_user_lang(context)
    field = INVENTORY_ADD_FIELDS[flow["step"]]
    text = (update.message.text or "").strip()
    question = strings.get(INVENTORY_ADD_QUESTIONS[field], lang)

    if field in ("qty", "min_qty"):
        if text in ("", "-"):
            text = "0"
        try:
            value = int(text)
        except ValueError:
            await _send_inventory_prompt(
                update,
                context,
                strings.get('INV_ERR_NUMBER', lang) + "\n\n" + question,
            )
            return states.SUPER_INVENTORY_INPUT
        if value < 0:
            await _send_inventory_prompt(
                update,
                context,
                strings.get('INV_ERR_NEGATIVE', lang) + "\n\n" + question,
            )
            return states.SUPER_INVENTORY_INPUT
    else:
        value = "" if text == "-" else text
        if field == "name" and not value:
            await _send_inventory_prompt(
                update,
                context,
                strings.get('INV_ERR_NAME', lang) + "\n\n" + question,
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
            strings.get('INV_ADD_FAILED', lang).format(
                error=strings.escape_md(result.get('error', 'unknown'))
            ),
            parse_mode="Markdown",
            reply_markup=keyboards.get_super_inventory_menu(lang),
        )
        return states.SUPER_INVENTORY_MENU

    db.log_action(
        _actor(update),
        "INVENTORY_ADD",
        f"{result['id']} {data['name']} qty={data['qty']}",
    )
    unit = f" {data['unit']}" if data["unit"] else ""
    await update.message.reply_text(
        strings.get('INV_ADD_SUCCESS', lang).format(
            id=strings.escape_md(result["id"]),
            name=strings.escape_md(data["name"]),
            qty=data["qty"],
            unit=strings.escape_md(unit),
        ),
        parse_mode="Markdown",
        reply_markup=keyboards.get_super_inventory_menu(lang),
    )
    return states.SUPER_INVENTORY_MENU


async def _inventory_adjust_input(update, context, flow):
    lang = get_user_lang(context)
    step = INVENTORY_ADJUST_STEPS[flow["step"]]
    text = (update.message.text or "").strip()

    if step == "item_id":
        if not text:
            await _send_inventory_prompt(
                update, context, strings.get('INV_ERR_ITEM', lang)
            )
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
                strings.get('INV_ERR_DIRECTION', lang),
                keyboards.get_inventory_direction_menu(lang),
            )
            return states.SUPER_INVENTORY_INPUT
    elif step == "qty":
        try:
            qty = int(text)
        except ValueError:
            await _send_inventory_prompt(
                update,
                context,
                strings.get('INV_ERR_NUMBER', lang)
                + "\n\n"
                + strings.get('INV_Q_ADJUST_QTY', lang),
            )
            return states.SUPER_INVENTORY_INPUT
        if qty <= 0:
            await _send_inventory_prompt(
                update,
                context,
                strings.get('INV_ERR_POSITIVE', lang)
                + "\n\n"
                + strings.get('INV_Q_ADJUST_QTY', lang),
            )
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
            message = strings.get('INV_ERR_NOT_FOUND', lang)
        elif error == "insufficient":
            message = strings.get('INV_ERR_INSUFFICIENT', lang).format(
                current=result.get('current')
            )
        else:
            message = strings.get('INV_ERR_GENERIC', lang).format(
                error=strings.escape_md(error or 'unknown')
            )
        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=keyboards.get_super_inventory_menu(lang),
        )
        return states.SUPER_INVENTORY_MENU

    db.log_action(
        _actor(update),
        "INVENTORY_ADJUST",
        f"{result['id']} {delta:+d} -> {result['new_qty']} ({data['reason']})",
    )
    await update.message.reply_text(
        strings.get('INV_UPDATE_SUCCESS', lang).format(
            id=strings.escape_md(result["id"]),
            name=strings.escape_md(result["name"]),
            current=result["current"],
            new_qty=result["new_qty"],
            delta=f"{delta:+d}",
            reason=strings.escape_md(data["reason"]),
        ),
        parse_mode="Markdown",
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
            strings.get('INV_DASHBOARD_UNAVAILABLE', lang),
            parse_mode="Markdown",
            reply_markup=keyboards.get_super_inventory_menu(lang),
        )
        return states.SUPER_INVENTORY_MENU

    url = f"{base_url}/inventory/{stats_web.create_inventory_token(ttl_seconds=7 * 24 * 3600)}"
    await update.message.reply_text(
        strings.get('INV_DASHBOARD_TITLE', lang),
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
