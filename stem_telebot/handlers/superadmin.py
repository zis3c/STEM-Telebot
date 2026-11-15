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
        [strings.get('BTN_SA_ADD_ADMIN', lang), strings.get('BTN_SA_DEL_ADMIN', lang)],
        [strings.get('BTN_SA_LIST_ADMIN', lang)],
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


async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_superadmin(update):
        return ConversationHandler.END
    admins = db.cached_sheet_admins
    
    if not admins:
        msg = "No secondary admins found."
    else:
        msg = f"*Secondary Admins ({len(admins)}):*\n" + "\n".join([f"`{a}`" for a in admins])
        
    await update.message.reply_text(msg, parse_mode="Markdown")
    return states.SUPER_ADMIN_MANAGE

async def add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_superadmin(update):
        return ConversationHandler.END
    lang = get_user_lang(context)
    await update.message.reply_text(
        strings.get('PROMPT_SA_ADD', lang),
        parse_mode="Markdown",
        reply_markup=keyboards.get_cancel_menu(lang)
    )
    return states.SUPER_ADD_ID

async def add_admin_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_superadmin(update):
        return ConversationHandler.END
    lang = get_user_lang(context)
    text = update.message.text.strip()
    
    if not text.isdigit():
        await update.message.reply_text(strings.get('ERR_SA_INVALID_ID', lang), parse_mode="Markdown")
        return states.SUPER_ADD_ID
        
    user_id = int(text)
    
    if db.is_admin(user_id):
        await update.message.reply_text(
            strings.get('ERR_SA_ALREADY_ADMIN', lang),
            parse_mode="Markdown",
            reply_markup=get_manage_admins_menu(lang)
        )
        return states.SUPER_ADMIN_MANAGE

    # Add to sheet
    if await run_db_call(db.add_admin, user_id, "Unknown", f"SA:{update.effective_user.id}"):
        await update.message.reply_text(strings.get('MSG_SA_ADDED', lang), parse_mode="Markdown", reply_markup=get_manage_admins_menu(lang))
        
        # Notify the new admin
        try:
            await context.bot.send_message(
                chat_id=user_id, 
                text=strings.get('MSG_SA_PROMOTED', lang),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Failed to notify new admin {user_id}: {e}")
            
        db.log_action(update.effective_user.first_name, "ADD_ADMIN", f"Promoted User {user_id}")
        return states.SUPER_ADMIN_MANAGE
    else:
        await update.message.reply_text("❌ DB Error", reply_markup=get_manage_admins_menu(lang))
        return states.SUPER_ADMIN_MANAGE

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
    if not await _require_superadmin(update):
        return ConversationHandler.END
    lang = get_user_lang(context)
    await update.message.reply_text(
        "*Inventory*\nChoose an action:",
        parse_mode="Markdown",
        reply_markup=keyboards.get_super_inventory_menu(lang),
    )
    return states.SUPER_INVENTORY_MENU


async def inventory_back_to_super(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    await update.message.reply_text(
        "🔙 Superadmin Dashboard",
        reply_markup=get_super_menu(lang)
    )
    return states.SUPER_MENU


async def inventory_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_superadmin(update):
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


async def inventory_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_superadmin(update):
        return ConversationHandler.END
    lang = get_user_lang(context)
    await update.message.reply_text(
        "Send the new item as:\n"
        "`Name | Category | Qty | Unit | Location | Min`\n\n"
        "Example: `A4 Paper | Consumable | 10 | ream | Store Room | 5`",
        parse_mode="Markdown",
        reply_markup=keyboards.get_cancel_menu(lang),
    )
    return states.SUPER_INVENTORY_ADD


async def inventory_add_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_superadmin(update):
        return ConversationHandler.END
    lang = get_user_lang(context)
    parts = [part.strip() for part in update.message.text.split("|")]

    def retry(message):
        return update.message.reply_text(
            message, reply_markup=keyboards.get_cancel_menu(lang)
        )

    if len(parts) < 3 or not parts[0]:
        await retry("❌ Format: Name | Category | Qty | Unit | Location | Min")
        return states.SUPER_INVENTORY_ADD
    try:
        qty = int(parts[2]) if parts[2] else 0
    except ValueError:
        await retry("❌ Qty must be a whole number.")
        return states.SUPER_INVENTORY_ADD
    try:
        min_qty = int(parts[5]) if len(parts) > 5 and parts[5] else 0
    except ValueError:
        await retry("❌ Min must be a whole number.")
        return states.SUPER_INVENTORY_ADD

    result = await run_db_call(
        db.add_inventory_item,
        parts[0],
        parts[1],
        qty,
        parts[3] if len(parts) > 3 else "",
        parts[4] if len(parts) > 4 else "",
        min_qty,
        _actor(update),
    )
    if not result.get("ok"):
        await retry(f"❌ Failed: {result.get('error')}")
        return states.SUPER_INVENTORY_ADD

    db.log_action(
        _actor(update), "INVENTORY_ADD", f"{result['id']} {parts[0]} qty={qty}"
    )
    unit = f" {parts[3]}" if len(parts) > 3 and parts[3] else ""
    await update.message.reply_text(
        f"✅ Added {result['id']} - {parts[0]} ({qty}{unit}).",
        reply_markup=keyboards.get_super_inventory_menu(lang),
    )
    return states.SUPER_INVENTORY_MENU


async def inventory_adjust_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_superadmin(update):
        return ConversationHandler.END
    lang = get_user_lang(context)
    await update.message.reply_text(
        "Send the stock change as:\n"
        "`ItemID | +/-Qty | Reason`\n\n"
        "Examples:\n"
        "`INV-001 | +20 | Restock from supplier`\n"
        "`INV-001 | -2 | Used for event`",
        parse_mode="Markdown",
        reply_markup=keyboards.get_cancel_menu(lang),
    )
    return states.SUPER_INVENTORY_ADJUST


async def inventory_adjust_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_superadmin(update):
        return ConversationHandler.END
    lang = get_user_lang(context)
    parts = [part.strip() for part in update.message.text.split("|")]

    def retry(message):
        return update.message.reply_text(
            message, reply_markup=keyboards.get_cancel_menu(lang)
        )

    if len(parts) < 2 or not parts[0]:
        await retry("❌ Format: ItemID | +/-Qty | Reason")
        return states.SUPER_INVENTORY_ADJUST
    try:
        delta = int(parts[1].replace(" ", ""))
    except ValueError:
        await retry("❌ Qty must be a whole number, e.g. +5 or -2.")
        return states.SUPER_INVENTORY_ADJUST

    reason = " | ".join(parts[2:]).strip() or "Manual update"
    result = await run_db_call(
        db.adjust_inventory, parts[0], delta, reason, _actor(update)
    )
    if not result.get("ok"):
        error = result.get("error")
        if error == "not_found":
            message = "❌ Item ID not found. Use List Stock to see IDs."
        elif error == "insufficient":
            message = f"❌ Not enough stock. Current: {result.get('current')}."
        elif error == "zero_delta":
            message = "❌ Change cannot be zero."
        else:
            message = f"❌ Failed: {error}"
        await retry(message)
        return states.SUPER_INVENTORY_ADJUST

    db.log_action(
        _actor(update),
        "INVENTORY_ADJUST",
        f"{result['id']} {delta:+d} -> {result['new_qty']} ({reason})",
    )
    await update.message.reply_text(
        f"✅ {result['id']} {result['name']}: "
        f"{result['current']} -> {result['new_qty']} ({reason})",
        reply_markup=keyboards.get_super_inventory_menu(lang),
    )
    return states.SUPER_INVENTORY_MENU


async def inventory_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_superadmin(update):
        return ConversationHandler.END
    lang = get_user_lang(context)
    base_url = _public_base_url()
    if not base_url:
        await update.message.reply_text(
            "❌ Set PUBLIC_BASE_URL or WEBHOOK_URL to share the dashboard.",
            reply_markup=keyboards.get_super_inventory_menu(lang),
        )
        return states.SUPER_INVENTORY_MENU

    url = f"{base_url}/inventory/{stats_web.create_inventory_token()}"
    await update.message.reply_text(
        "*Inventory Dashboard*\n"
        "_Read-only link. Share it with the team; it does not expire._",
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
