from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ConversationHandler, ContextTypes
import strings
import keyboards
import states
from database import db
import logging
import re
import asyncio
import os
import time
from datetime import datetime, timedelta
from io import BytesIO
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

KL_TZ = ZoneInfo("Asia/Kuala_Lumpur")
LOG_DATE_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2}\]")
TRUSTED_RECEIPT_URL_RE = re.compile(
    r"^https://(?:drive\.google\.com|docs\.google\.com|lh3\.googleusercontent\.com)/",
    re.IGNORECASE,
)
_DAILY_LOG_LOCK = asyncio.Lock()

_VERIF_WINDOW_SECONDS = 10 * 60
_VERIF_LOCK_SECONDS = 15 * 60
_VERIF_MAX_USER_ATTEMPTS = 6
_VERIF_MAX_MATRIC_ATTEMPTS = 12
_verif_user_state = {}
_verif_matric_state = {}


def _touch_verif_state(store, key, now_ts):
    state = store.get(key)
    if not state:
        state = {"window_start": now_ts, "attempts": 0, "locked_until": 0}
        store[key] = state

    if now_ts >= state["locked_until"] and (now_ts - state["window_start"]) > _VERIF_WINDOW_SECONDS:
        state["window_start"] = now_ts
        state["attempts"] = 0
    return state


def _check_verif_limit(user_id: int, matric: str):
    now_ts = time.time()
    user_state = _touch_verif_state(_verif_user_state, user_id, now_ts)
    matric_state = _touch_verif_state(_verif_matric_state, matric, now_ts)

    user_retry = max(0, int(user_state["locked_until"] - now_ts))
    matric_retry = max(0, int(matric_state["locked_until"] - now_ts))
    retry_after = max(user_retry, matric_retry)
    return retry_after > 0, retry_after


def _mark_verif_attempt(user_id: int, matric: str, success: bool):
    now_ts = time.time()
    user_state = _touch_verif_state(_verif_user_state, user_id, now_ts)
    matric_state = _touch_verif_state(_verif_matric_state, matric, now_ts)

    if success:
        user_state["attempts"] = 0
        matric_state["attempts"] = 0
        user_state["window_start"] = now_ts
        matric_state["window_start"] = now_ts
        return

    user_state["attempts"] += 1
    matric_state["attempts"] += 1

    if user_state["attempts"] >= _VERIF_MAX_USER_ATTEMPTS:
        user_state["locked_until"] = now_ts + _VERIF_LOCK_SECONDS
    if matric_state["attempts"] >= _VERIF_MAX_MATRIC_ATTEMPTS:
        matric_state["locked_until"] = now_ts + _VERIF_LOCK_SECONDS


def _mask_sensitive_in_text(text: str) -> str:
    if not text:
        return ""

    val = str(text)

    # Mask email local-part.
    val = re.sub(r'([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})', r'\1***@\2', val)

    # Mask 4+ digit numeric chunks.
    def _mask_digits(match):
        s = match.group(0)
        if len(s) <= 4:
            return "*" * len(s)
        return s[:2] + ("*" * (len(s) - 4)) + s[-2:]

    val = re.sub(r"\b\d{4,}\b", _mask_digits, val)
    return val


def _escape_md(text):
    return (
        str(text or "")
        .replace("\\", "\\\\")
        .replace("_", "\\_")
        .replace("*", "\\*")
        .replace("`", "\\`")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("(", "\\(")
    )


def _receipt_md_value(value):
    raw = str(value or "").strip()
    if raw.startswith("http") and TRUSTED_RECEIPT_URL_RE.match(raw):
        safe_url = raw.replace(")", "%29")
        return f"[View Receipt]({safe_url})"
    return _escape_md(raw)


# --- HELPERS ---
def get_user_lang(context: ContextTypes.DEFAULT_TYPE):
    """Retrieve user language, default to EN."""
    return context.user_data.get('lang', strings.DEFAULT_LANG)

async def run_db_call(func, *args, **kwargs):
    """Runs blocking DB/sheets work on a thread so the event loop stays responsive."""
    return await asyncio.to_thread(func, *args, **kwargs)

async def check_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global keyword checker for main menu navigation (Multi-lingual matches)"""
    text = update.message.text.strip()
    
    # Check against all language variations
    if text in strings.get_all('BTN_CHECK'): return await check_start(update, context)
    if text in strings.get_all('BTN_HELP'): return await help_command(update, context)
    if text in strings.get_all('BTN_SETTINGS'): return await settings_menu(update, context)
    if text in strings.get_all('BTN_LANGUAGES'): return await languages_menu(update, context)
    if text in strings.get_all('BTN_BACK'): return await start(update, context) # Default back to main, but sub-menus might handle back differently
    return None

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.setdefault('lang', strings.DEFAULT_LANG) # Init lang if missing
    lang = get_user_lang(context)
    
    user = update.effective_user
    
    # Maintenance Check
    if db.maintenance_mode and not db.is_admin(user.id):
        await update.message.reply_text("🚧 *System Under Maintenance*\nPlease try again later.", parse_mode="Markdown")
        return ConversationHandler.END

    # Send Welcome Message with Main Menu (Includes Web App registration button)
    await update.message.reply_text(
        strings.get('WELCOME_MSG', lang).format(name=user.first_name), 
        reply_markup=keyboards.get_main_menu(lang), 
        parse_mode="Markdown"
    )

    # Log user for broadcast (Done in background to improve speed)
    try:
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, db.log_user, user.id, user.first_name)
    except Exception as e:
        logger.error(f"Log user fail: {e}")
    return ConversationHandler.END

async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    await update.message.reply_text(
        "⚙️ *Settings*", # Header
        parse_mode="Markdown",
        reply_markup=keyboards.get_settings_menu(lang)
    )
    return ConversationHandler.END

async def languages_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    await update.message.reply_text(
        strings.get('MSG_SELECT_LANG', lang),
        parse_mode="Markdown",
        reply_markup=keyboards.get_language_menu(lang)
    )
    return ConversationHandler.END

async def registration_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    db.log_action(update.effective_user.first_name, "OPEN_REGISTRATION", "Viewed Benefits", role="USER")
    await update.message.reply_text(
        strings.get('REGISTRATION_MSG', lang),
        parse_mode="Markdown",
        reply_markup=keyboards.get_become_member_keyboard(lang)
    )
    return ConversationHandler.END

async def set_lang_en(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['lang'] = 'EN'
    db.log_action(update.effective_user.first_name, "SET_LANG", "English", role="USER")
    # Return to Settings Menu to show context
    await update.message.reply_text(
        strings.get('MSG_LANG_CHANGED', 'EN'),
        reply_markup=keyboards.get_settings_menu('EN')
    )
    return ConversationHandler.END

async def set_lang_ms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['lang'] = 'MS'
    db.log_action(update.effective_user.first_name, "SET_LANG", "Bahasa Melayu", role="USER")
    # Return to Settings Menu to show context
    await update.message.reply_text(
        strings.get('MSG_LANG_CHANGED', 'MS'),
        reply_markup=keyboards.get_settings_menu('MS')
    )
    return ConversationHandler.END



async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    await update.message.reply_text(
        strings.get('HELP_MSG', lang),
        parse_mode="Markdown",
        reply_markup=keyboards.get_help_inline_keyboard(lang)
    )
    return ConversationHandler.END


async def how_it_works_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Switch to detailed how-it-works view in the same message bubble."""
    query = update.callback_query
    await query.answer()

    lang = get_user_lang(context)
    await query.edit_message_text(
        strings.get('HOW_IT_WORKS_MSG', lang),
        parse_mode="Markdown",
        reply_markup=keyboards.get_help_back_inline_keyboard(lang),
        disable_web_page_preview=True,
    )


async def help_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return to the main help view in the same message bubble."""
    query = update.callback_query
    await query.answer()

    lang = get_user_lang(context)
    await query.edit_message_text(
        strings.get('HELP_MSG', lang),
        parse_mode="Markdown",
        reply_markup=keyboards.get_help_inline_keyboard(lang),
    )

async def check_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    await update.message.reply_text(
        strings.get('PROMPT_MATRIC', lang),
        parse_mode="Markdown",
        reply_markup=keyboards.get_cancel_menu(lang)
    )
    return states.ASK_MATRIC

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    await update.message.reply_text(strings.get('ERR_CANCEL', lang), reply_markup=keyboards.get_main_menu(lang))
    return ConversationHandler.END

async def receive_matric(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    text = update.message.text.strip().upper()
    
    # Check Cancel
    if text in strings.get_all('BTN_CANCEL') or text == "CANCEL": 
        return await cancel(update, context)
    
    # Handle "Try Again"
    if text in strings.get_all('BTN_TRY_AGAIN'):
        await update.message.reply_text(strings.get('PROMPT_MATRIC', lang), parse_mode="Markdown", reply_markup=keyboards.get_cancel_menu(lang))
        return states.ASK_MATRIC

    # Global Navigation Check
    nav = await check_keywords(update, context)
    if nav is not None: return nav

    if not re.match(r'^[A-Z0-9]{6,15}$', text):
        await update.message.reply_text(
            strings.get('ERR_INVALID_MATRIC', lang), 
            parse_mode="Markdown",
            reply_markup=keyboards.get_retry_menu(lang)
        )
        return states.ASK_MATRIC
    
    context.user_data['matric'] = text
    await update.message.reply_text(
        strings.get('PROMPT_IC', lang).format(matric=text),
        parse_mode="Markdown",
        reply_markup=keyboards.get_cancel_menu(lang)
    )
    return states.ASK_IC

async def receive_ic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    text = update.message.text.strip()
    
    if text in strings.get_all('BTN_CANCEL') or text == "CANCEL": return await cancel(update, context)

    # Handle "Try Again"
    if text in strings.get_all('BTN_TRY_AGAIN'):
        user_matric = context.user_data.get('matric', 'Unknown')
        await update.message.reply_text(
            strings.get('PROMPT_IC', lang).format(matric=user_matric),
            parse_mode="Markdown",
            reply_markup=keyboards.get_cancel_menu(lang)
        )
        return states.ASK_IC

    # Global Navigation Check
    nav = await check_keywords(update, context)
    if nav is not None: return nav

    if not re.match(r'^\d{4}$', text):
        await update.message.reply_text(
            strings.get('ERR_INVALID_IC', lang), 
            parse_mode="Markdown",
            reply_markup=keyboards.get_retry_menu(lang)
        )
        return states.ASK_IC
    
    # Optimized: No "Verifying..." message. Cache is instant. 
    # Sending/Deleting message takes 2 extra API calls (SLOW).
    # loading_msg = await update.message.reply_text(strings.get('PROMPT_LOADING', lang), parse_mode="Markdown")
    
    user_matric = context.user_data['matric']
    user_ic_last4 = text
    limited, retry_after = _check_verif_limit(update.effective_user.id, user_matric)
    if limited:
        lock_msg = "Too many verification attempts. Please try again later."
        if lang == "MS":
            lock_msg = "Terlalu banyak cubaan pengesahan. Sila cuba lagi kemudian."
        await update.message.reply_text(
            f"{lock_msg} ({retry_after}s)",
            reply_markup=keyboards.get_main_menu(lang),
        )
        return ConversationHandler.END

    msg = strings.get('ERR_DB_CONNECTION', lang)
    verification_ok = False
    generic_fail_msg = "*Verification Failed*\nYour details could not be verified."
    if lang == "MS":
        generic_fail_msg = "*Pengesahan Gagal*\nMaklumat anda tidak dapat disahkan."
    
    try:
        row_values, row_index = await run_db_call(db.find_member, user_matric)
        
        if row_values:
            if len(row_values) > 9: # Need at least up to IC (Index 9)
                # Gspread List 0-index values: A=0(Timestamp), C=2(Name), D=3(Matric), E=4(Courses/Prog)
                # J=9(IC), Q=16(Receipt), R=17(Status)
                db_timestamp = row_values[0]
                db_name = row_values[2] 
                db_ic = str(row_values[9]).strip().replace(" ", "") # J is 9
                db_prog = row_values[4] # E is 4
                db_prog_short = strings.format_program_short(db_prog)
                # Col Q (index 16) is Receipt, Col R (index 17) is Status
                db_resit = str(row_values[16]).strip() if len(row_values) > 16 else ""
                db_status_raw = str(row_values[17]).strip() if len(row_values) > 17 else ""
                db_status_norm = " ".join(db_status_raw.lower().split())
                membership_id = str(row_values[15]).strip() if len(row_values) > 15 else ""

                # Accept flow with legacy compatibility:
                # - old rows can use symbols (✓/✅) or custom words instead of "Approved"
                # - some rows are effectively approved if Membership ID already exists
                approved_tokens = (
                    "approved", "verified", "verify", "accept", "accepted",
                    "disahkan", "lulus", "aktif", "valid"
                )
                rejected_tokens = (
                    "rejected", "reject", "tolak", "ditolak", "batal", "cancel"
                )
                pending_tokens = (
                    "pending", "proses", "review", "semakan"
                )

                final_status = "Pending"
                if any(tok in db_status_norm for tok in approved_tokens):
                    final_status = "Approved"
                elif (
                    any(tok in db_status_norm for tok in rejected_tokens)
                ):
                    final_status = "Rejected"
                elif any(tok in db_status_norm for tok in pending_tokens):
                    final_status = "Pending"
                elif membership_id and membership_id != "-":
                    # Fallback for historical rows with empty/non-standard status.
                    final_status = "Approved"
                elif not db_status_norm:
                    final_status = "Pending"

                if db_ic.endswith(user_ic_last4):
                    verification_ok = True
                    if final_status == "Approved": 
                        if not membership_id or membership_id == "-":
                            # Fallback if ID not generated yet but status is Approved
                            msg = strings.get('STATUS_PENDING', lang)
                        else:
                            # Format Date: 12/20/2025 (from db_timestamp)
                            date_of_entry = db_timestamp.split(' ')[0]
                            try:
                                dt = None
                                if '-' in date_of_entry:
                                    dt = datetime.strptime(date_of_entry, "%Y-%m-%d")
                                elif '/' in date_of_entry:
                                    try:
                                        dt = datetime.strptime(date_of_entry, "%m/%d/%Y")
                                    except ValueError:
                                        dt = datetime.strptime(date_of_entry, "%d/%m/%Y")
                                
                                if dt:
                                    date_of_entry = dt.strftime("%d/%m/%y")
                            except ValueError:
                                pass

                            msg = strings.get('VERIFICATION_SUCCESS', lang).format(
                                membership_id=membership_id,
                                name=db_name,
                                matric=user_matric,
                                program=db_prog_short,
                                date=date_of_entry
                            )
                    elif final_status == "Pending":
                        msg = strings.get('STATUS_PENDING', lang)
                    elif final_status == "Rejected":
                         msg = strings.get('STATUS_REJECT', lang)
                    else:
                         msg = strings.get('STATUS_PENDING', lang) 
                else:
                     msg = generic_fail_msg
            else:
                    msg = generic_fail_msg
        else:
            msg = generic_fail_msg
                
    except Exception as e:
        logger.error(e)
        verification_ok = False

    # AUTO DELETE LOADING MESSAGE
    # AUTO DELETE LOADING MESSAGE (Removed for speed cleanup)
    # try:
    #     await loading_msg.delete()
    # except Exception:
    #     pass 

    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboards.get_main_menu(lang))
    _mark_verif_attempt(update.effective_user.id, user_matric, verification_ok)
    
    # Log the result
    log_status = "SUCCESS" if verification_ok else "FAILED_VERIFY"
    db.log_action(
        update.effective_user.first_name,
        "CHECK_MEMBERSHIP",
        f"Matric: {_mask_sensitive_in_text(user_matric)} | Result: {log_status}",
        role="USER"
    )
    
    return ConversationHandler.END

# --- LOGGING HANDLER (GROUP -1) ---
async def log_any_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Logs ALL user interactions for anomaly detection."""
    user = update.effective_user
    if not user: return
    
    # Handle non-text messages
    if not update.message or not update.message.text:
        msg_type = "MEDIA/OTHER"
        if update.message:
            if update.message.sticker: msg_type = "STICKER"
            elif update.message.photo: msg_type = "PHOTO"
            elif update.message.document: msg_type = "DOCUMENT"
            elif update.message.voice: msg_type = "VOICE"
        db.log_action(f"{user.first_name} ({user.id})", "MSG_NON_TEXT", msg_type, role="USER")
        return

    text = update.message.text.strip()
    
    # Identify Keyboard Clicks
    action = "MSG"
    details = f"Text({len(text)} chars)"
    
    # All Button Keys from strings.py
    btn_keys = [
        'BTN_CHECK', 'BTN_HELP', 'BTN_SETTINGS', 'BTN_LANGUAGES', 'BTN_BACK', 'BTN_CANCEL', 
        'BTN_TRY_AGAIN', 'BTN_BECOME_MEMBER', 'BTN_LANG_EN', 'BTN_LANG_MS',
        'BTN_ADMIN_MANAGE', 'BTN_ADMIN_BROADCAST', 'BTN_ADMIN_STATS', 'BTN_ADMIN_EXIT',
        'BTN_ADMIN_DEL', 'BTN_ADMIN_LIST', 'BTN_ADMIN_SEARCH', 'BTN_ADMIN_CHECK_PENDING',
        'BTN_SA_MAINTENANCE', 'BTN_SA_ADMINS', 'BTN_SA_HEALTH', 'BTN_SA_REFRESH', 'BTN_SA_LOGS'
    ]
    
    for key in btn_keys:
        if text in strings.get_all(key):
            action = "KEYBOARD_CLICK"
            details = f"Button: {key} ({text})"
            break

    db.log_action(
        f"{user.first_name} ({user.id})",
        action,
        _mask_sensitive_in_text(details),
        role="USER",
    )

# --- JOB QUEUE & CALLBACKS ---
async def check_pending_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual trigger to check pending registrations immediately."""
    user_id = update.effective_user.id
    if not db.is_admin(user_id): return
    
    await update.message.reply_text("🔎 Scanning for pending registrations...")
    await check_registrations(context)
    await update.message.reply_text("✅ Scan complete.")

async def check_registrations(context: ContextTypes.DEFAULT_TYPE):
    """Job to check for new unprocessed registrations."""
    try:
        new_regs = await run_db_call(db.get_unprocessed_registrations)
        if not new_regs: return
        
        # Notify ALL Admins (Super + Env + Sheet)
        admins = await run_db_call(db.get_all_admin_ids)
        for reg in new_regs:
            row_idx = reg['row']
            data = reg['data']
            # data: [time, email, name, matric, courses, ..., ic, ..., receipt(16), status(17)]
            name = data[2]
            matric = data[3]
            resit_url = data[16] if len(data) > 16 else "No Receipt"

            safe_name = _escape_md(name)
            safe_matric = _escape_md(matric)
            
            # Handle Receipt URL (often contains underscores)
            receipt_display = _receipt_md_value(resit_url)
            
            msg = (
                f"*NEW REGISTRATION 🔔*\n\n"
                f"Name: *{safe_name}*\n"
                f"Matric: *{safe_matric}*\n"
                f"Receipt: {receipt_display}"
            )
            
            review_keyboard = keyboards.get_admin_review_keyboard(row_idx, matric, "EN")

            # Send to all admins
            for admin_id in admins:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=msg,
                        parse_mode="Markdown",
                        reply_markup=review_keyboard
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin {admin_id}: {e}")
            
            # Mark pending so the bot does not notify repeatedly.
            await run_db_call(db.update_status, row_idx, "Pending")
            
    except Exception as e:
        logger.error(f"Check Regs Error: {e}")

def _build_review_summary(row_values):
    name = _escape_md(row_values[2] if len(row_values) > 2 else "-")
    matric = _escape_md(row_values[3] if len(row_values) > 3 else "-")
    receipt = row_values[16] if len(row_values) > 16 else "-"
    receipt_md = _receipt_md_value(receipt)
    return (
        f"*NEW REGISTRATION*\n\n"
        f"Name: *{name}*\n"
        f"Matric: *{matric}*\n"
        f"Receipt: {receipt_md}"
    )

async def review_accept_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_user_lang(context)

    if not db.is_admin(query.from_user.id):
        await query.answer("Admins only.", show_alert=True)
        return

    try:
        _, row_raw, matric = query.data.split(":", 2)
        row_idx = int(row_raw)
    except Exception:
        await query.edit_message_text("Invalid action payload.")
        return

    await query.edit_message_text(
        f"Confirm accept for *{_escape_md(matric)}*?",
        parse_mode="Markdown",
        reply_markup=keyboards.get_admin_confirm_keyboard("accept", row_idx, matric, lang)
    )

async def review_reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_user_lang(context)

    if not db.is_admin(query.from_user.id):
        await query.answer("Admins only.", show_alert=True)
        return

    try:
        _, row_raw, matric = query.data.split(":", 2)
        row_idx = int(row_raw)
    except Exception:
        await query.edit_message_text("Invalid action payload.")
        return

    await query.edit_message_text(
        f"Confirm reject for *{_escape_md(matric)}*?\nThis will remove the record from database.",
        parse_mode="Markdown",
        reply_markup=keyboards.get_admin_confirm_keyboard("reject", row_idx, matric, lang)
    )

async def review_do_accept_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not db.is_admin(query.from_user.id):
        await query.answer("Admins only.", show_alert=True)
        return

    try:
        _, row_raw, matric = query.data.split(":", 2)
        row_idx = int(row_raw)
    except Exception:
        await query.edit_message_text("Invalid action payload.")
        return

    ok = await run_db_call(db.update_status_by_row_or_matric, row_idx, matric, "Approved")
    if ok:
        db.log_action(
            f"{query.from_user.first_name} ({query.from_user.id})",
            "ACCEPT_MEMBER",
            f"Matric: {matric} | Row: {row_idx}",
            role="ADMIN"
        )
        await query.edit_message_text(
            f"Accepted: *{_escape_md(matric)}*\nMember kept in database.",
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(
            f"Could not accept `{_escape_md(matric)}`\nRecord may have moved or been removed.",
            parse_mode="Markdown"
        )

async def review_do_reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not db.is_admin(query.from_user.id):
        await query.answer("Admins only.", show_alert=True)
        return

    try:
        _, row_raw, matric = query.data.split(":", 2)
        row_idx = int(row_raw)
    except Exception:
        await query.edit_message_text("Invalid action payload.")
        return

    ok = await run_db_call(db.delete_registration_by_row_or_matric, row_idx, matric)
    if ok:
        db.log_action(
            f"{query.from_user.first_name} ({query.from_user.id})",
            "REJECT_MEMBER",
            f"Matric: {matric} | Row: {row_idx} | Action: Removed",
            role="ADMIN"
        )
        await query.edit_message_text(
            f"Rejected: *{_escape_md(matric)}*\nRecord removed from database.",
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(
            f"Could not reject `{_escape_md(matric)}`\nRecord may have moved or been removed.",
            parse_mode="Markdown"
        )

async def review_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Action cancelled.")
    lang = get_user_lang(context)
    try:
        _, row_raw, matric = query.data.split(":", 2)
        row_idx = int(row_raw)
    except Exception:
        await query.edit_message_text("Action cancelled.")
        return

    row_values, _ = await run_db_call(db.get_member_by_row_or_matric, row_idx, matric)
    if not row_values:
        await query.edit_message_text("Action cancelled. Record not found anymore.")
        return

    await query.edit_message_text(
        _build_review_summary(row_values),
        parse_mode="Markdown",
        reply_markup=keyboards.get_admin_review_keyboard(row_idx, matric, lang)
    )

async def review_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_user_lang(context)

    if not db.is_admin(query.from_user.id):
        await query.answer("Admins only.", show_alert=True)
        return

    try:
        _, row_raw, matric = query.data.split(":", 2)
        row_idx = int(row_raw)
    except Exception:
        await query.answer("Invalid detail payload.", show_alert=True)
        return

    row_values, _ = await run_db_call(db.get_member_by_row_or_matric, row_idx, matric)
    if not row_values:
        await query.answer("Record not found.", show_alert=True)
        return

    # Enrich pending-detail output with latest cached row for the same matric,
    # so fields generated later (USAS email, entry date, ID, invoice, receipt)
    # still appear when available.
    cached_row, _ = await run_db_call(db.find_member, str(matric).strip().upper())
    if cached_row:
        max_len = max(len(row_values), len(cached_row))
        merged = []
        for i in range(max_len):
            primary = row_values[i] if i < len(row_values) else ""
            fallback = cached_row[i] if i < len(cached_row) else ""
            merged.append(primary if str(primary).strip() else fallback)
        row_values = merged

    def v(idx):
        return str(row_values[idx]).strip() if len(row_values) > idx and row_values[idx] is not None else "-"

    name = v(2)
    matric_v = v(3)
    prog = strings.format_program_short(v(4))
    sem = v(5)
    phone = v(6)
    personal_email = v(7)
    usas_email = v(8)
    ic = v(9)
    birthday = v(10)
    birthplace = v(11)
    address = v(12)
    entry_raw = v(13)
    minute_no = v(14)
    membership_id = v(15)
    proof_url = v(16)
    status = v(17)
    receipt_url = v(18)
    invoice_no = v(19)

    entry_display = entry_raw
    try:
        if entry_raw and entry_raw != "-":
            dt = None
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(entry_raw.split(" ")[0], fmt)
                    break
                except ValueError:
                    continue
            if dt:
                entry_display = dt.strftime("%d-%b-%y").lstrip("0")
    except Exception:
        entry_display = entry_raw

    proof_display = "Proof PDF" if proof_url.startswith("http") else proof_url
    receipt_display = "Download PDF" if receipt_url.startswith("http") else receipt_url

    details_text = (
        f"👤 {name}\n"
        f"🆔 {matric_v}\n"
        f"🎓 Prog: {prog} | Sem: {sem}\n"
        f"📞 {phone}\n"
        f"📧 {personal_email}\n"
        f"🏫 {usas_email}\n"
        f"🪪 IC: {ic}\n"
        f"🎂 {birthday} ({birthplace})\n"
        f"🏠 {address}\n"
        f"📅 Entry: {entry_display}\n"
        f"⏱️ Min: {minute_no}\n"
        f"🔑 ID: {membership_id}\n"
        f"📄 Proof: {proof_display}\n"
        f"🧾 Invoice: {invoice_no}\n"
        f"📎 Receipt: {receipt_display}\n"
        f"✅ Status: {status}"
    )

    await query.edit_message_text(
        details_text,
        reply_markup=keyboards.get_admin_review_detail_keyboard(row_idx, matric, lang)
    )

async def review_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_user_lang(context)

    if not db.is_admin(query.from_user.id):
        await query.answer("Admins only.", show_alert=True)
        return

    try:
        _, row_raw, matric = query.data.split(":", 2)
        row_idx = int(row_raw)
    except Exception:
        await query.edit_message_text("Invalid action payload.")
        return

    row_values, _ = await run_db_call(db.get_member_by_row_or_matric, row_idx, matric)
    if not row_values:
        await query.edit_message_text("Record not found.")
        return

    await query.edit_message_text(
        _build_review_summary(row_values),
        parse_mode="Markdown",
        reply_markup=keyboards.get_admin_review_keyboard(row_idx, matric, lang)
    )

async def send_daily_logs(context: ContextTypes.DEFAULT_TYPE):
    """Send only yesterday's logs (KL time), once per report day."""
    if _DAILY_LOG_LOCK.locked():
        return

    async with _DAILY_LOG_LOCK:
        target_date = (datetime.now(KL_TZ).date() - timedelta(days=1)).strftime("%Y-%m-%d")
        if await run_db_call(db.get_last_maintenance) == target_date:
            return

        filename = "activity.log"
        if not os.path.exists(filename):
            await run_db_call(db.update_last_maintenance, target_date)
            return

        try:
            with open(filename, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            logger.error(f"Failed to read activity.log: {e}")
            return

        if not lines:
            await run_db_call(db.update_last_maintenance, target_date)
            return

        report_lines = []
        keep_lines = []
        for line in lines:
            match = LOG_DATE_RE.match(line)
            if match and match.group(1) == target_date:
                report_lines.append(line)
            else:
                keep_lines.append(line)

        # Nothing from yesterday: mark processed so it won't keep retrying.
        if not report_lines:
            await run_db_call(db.update_last_maintenance, target_date)
            return

        report_content = "".join(report_lines)
        report_name = f"Logs_{target_date}.txt"
        sent_count = 0
        for uid in db.superadmin_ids:
            try:
                payload = BytesIO(report_content.encode("utf-8"))
                payload.name = report_name
                await context.bot.send_document(
                    chat_id=uid,
                    document=payload,
                    filename=report_name,
                    caption="📜 Daily Admin Logs"
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send logs to {uid}: {e}")

        # Keep logs if nobody received them (retry next run).
        if sent_count == 0:
            return

        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.writelines(keep_lines)
            await run_db_call(db.update_last_maintenance, target_date)
            logger.info(f"Daily logs sent for {target_date}.")
        except Exception as e:
            logger.error(f"Failed to rotate activity.log: {e}")
