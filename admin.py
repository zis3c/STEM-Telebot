from telegram import Update
from telegram.ext import ConversationHandler, ContextTypes
import strings
import keyboards
import states
import handlers
from database import db
import logging
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Helper to get lang (Admins might use local too)
def get_user_lang(context: ContextTypes.DEFAULT_TYPE):
    return context.user_data.get('lang', strings.DEFAULT_LANG)

async def run_db_call(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


def _parse_membership_datetime(raw_value):
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text or text == "-":
        return None
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
        "%d/%m/%y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _is_row_expired(row):
    status_raw = str(row[17]).strip().lower() if len(row) > 17 else ""
    if any(tok in status_raw for tok in ("expired", "expire", "tamat", "luput")):
        return True

    entry_raw = row[13] if len(row) > 13 and str(row[13]).strip() else (row[0] if len(row) > 0 else "")
    entry_dt = _parse_membership_datetime(entry_raw)
    if not entry_dt:
        return False
    return datetime.now() >= (entry_dt + timedelta(days=365))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    user_id = update.effective_user.id
    if not db.is_admin(user_id):
        # Security: Silent fail for unauthorized users
        return ConversationHandler.END
    
    await update.message.reply_text(
        strings.get('ADMIN_DASHBOARD', lang), 
        parse_mode="Markdown", 
        reply_markup=keyboards.get_admin_menu(lang)
    )
    return states.ADMIN_MENU

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    try:
        data = await run_db_call(db.get_stats)
        stats_month_year = datetime.now().strftime("%B %Y")

        def escape_md(text):
            return str(text).replace('_', '\\_').replace('*', '\\*').replace('`', '\\`').replace('[', '\\[')

        month_names = data.get('registered_current_month_names', [])
        max_listed_names = 20
        if month_names:
            listed = [f"- {escape_md(name)}" for name in month_names[:max_listed_names]]
            if len(month_names) > max_listed_names:
                listed.append(f"_...and {len(month_names) - max_listed_names} more._")
            registered_current_month_list = "\n".join(listed)
        else:
            registered_current_month_list = "-"

        await update.message.reply_text(
            strings.get('ADMIN_STATS', lang).format(
                stats_month_year=stats_month_year,
                total_last_30=data['total_last_30'],
                approved_last_30=data['approved_last_30'],
                rejected_last_30=data['rejected_last_30'],
                pending_current=data['pending_current'],
                approval_rate=data['approval_rate'],
                expiring_next_30=data['expiring_next_30'],
                expired_this_month=data['expired_this_month'],
                registered_current_month_count=data['registered_current_month_count'],
                registered_current_month_list=registered_current_month_list,
            ), 
            parse_mode="Markdown",
            reply_markup=keyboards.get_admin_menu(lang)
        )
    except Exception as e:
        logger.error(e)
        await update.message.reply_text(strings.get('ERR_DB_CONNECTION', lang))
    return states.ADMIN_MENU

async def check_pending_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """List all pending members requiring admin review."""
    lang = get_user_lang(context)
    loading = await update.message.reply_text(strings.get('ADMIN_SEARCHING', lang))
    try:
        pending = await run_db_call(db.get_members_by_filter, "Pending")
        if not pending:
            await loading.edit_text(strings.get('ADMIN_PENDING_EMPTY', lang))
            await update.message.reply_text(
                strings.get('ADMIN_DASHBOARD', lang),
                parse_mode="Markdown",
                reply_markup=keyboards.get_admin_menu(lang)
            )
            return states.ADMIN_MENU

        await loading.edit_text(
            strings.get('ADMIN_PENDING_HEADER', lang).format(count=len(pending)),
            parse_mode="Markdown"
        )

        def esc(t):
            return str(t).replace('_', '\\_').replace('*', '\\*').replace('`', '\\`').replace('[', '\\[')

        for item in pending[:30]:
            row_idx = item.get('row')
            matric = esc(item.get('matric', '-'))
            row, _ = await run_db_call(db.get_member_by_row_or_matric, row_idx, matric)

            if row:
                def escape_md(text):
                    return str(text).replace('_', '\\_').replace('*', '\\*').replace('`', '\\`').replace('[', '\\[')

                def safe_get(idx):
                    return escape_md(row[idx] if len(row) > idx else "-")

                raw_receipt = row[18] if len(row) > 18 else "-"
                receipt_display = f"[Download PDF]({raw_receipt})" if str(raw_receipt).startswith("http") else escape_md(raw_receipt)

                raw_proof = row[16] if len(row) > 16 else "-"
                if "drive.google.com" in str(raw_proof) and "id=" in str(raw_proof):
                    raw_proof = str(raw_proof).replace("open?", "uc?export=download&")
                proof_display = f"[Proof PDF]({raw_proof})" if str(raw_proof).startswith("http") else escape_md(raw_proof)
                prog_display = escape_md(strings.format_program_short(row[4] if len(row) > 4 else "-"))

                detail_card = (
                    f"\U0001F464 *{safe_get(2)}*\n"
                    f"\U0001F194 `{safe_get(3)}`\n"
                    f"\U0001F393 Prog: {prog_display} | Sem: {safe_get(5)}\n"
                    f"\U0001F4DE {safe_get(6)}\n"
                    f"\U0001F4E7 {safe_get(7)}\n"
                    f"\U0001F3EB {safe_get(8)}\n"
                    f"\U0001FAAA IC: {safe_get(9)}\n"
                    f"\U0001F382 {safe_get(10)} ({safe_get(11)})\n"
                    f"\U0001F3E0 {safe_get(12)}\n"
                    f"\U0001F4C5 Entry: {safe_get(13)}\n"
                    f"\u23F1\uFE0F Min: {safe_get(14)}\n"
                    f"\U0001F511 ID: `{safe_get(15)}`\n"
                    f"\U0001F4C4 Proof: {proof_display}\n"
                    f"\U0001F9FE Invoice: `{safe_get(19)}`\n"
                    f"\U0001F4CE Receipt: {receipt_display}\n"
                    f"\u2705 Status: {safe_get(17)}"
                )
            else:
                name = esc(item.get('name', '-'))
                prog = esc(strings.format_program_short(item.get('prog', '-')))
                detail_card = (
                    f"\U0001F464 *{name}*\n"
                    f"\U0001F194 `{matric}`\n"
                    f"\U0001F393 Prog: {prog}\n"
                    f"\u2705 Status: *Pending*"
                )

            await update.message.reply_text(
                detail_card,
                parse_mode="Markdown",
                reply_markup=keyboards.get_admin_review_keyboard(row_idx, matric, lang)
            )

        await update.message.reply_text(
            strings.get('ADMIN_DASHBOARD', lang),
            parse_mode="Markdown",
            reply_markup=keyboards.get_admin_menu(lang)
        )
        return states.ADMIN_MENU
    except Exception as e:
        logger.error(f"Pending list error: {e}")
        await loading.edit_text(strings.get('ERR_DB_CONNECTION', lang))
        await update.message.reply_text(
            strings.get('ADMIN_DASHBOARD', lang),
            parse_mode="Markdown",
            reply_markup=keyboards.get_admin_menu(lang)
        )
        return states.ADMIN_MENU
# --- MANAGE MEMBERS MENU ---
async def manage_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    await update.message.reply_text(
        strings.get('BTN_ADMIN_MANAGE', lang), 
        parse_mode="Markdown", 
        reply_markup=keyboards.get_admin_manage_menu(lang)
    )
    return states.ADMIN_MANAGE

async def back_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Used for "Back" button inside Manage Menu
    return await start(update, context)

async def back_to_manage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Used for "Cancel" inside Add/Del/Search flows.
    lang = get_user_lang(context)
    await update.message.reply_text(
        strings.get('BTN_ADMIN_MANAGE', lang),
        reply_markup=keyboards.get_admin_manage_menu(lang)
    )
    return states.ADMIN_MANAGE

# --- LIST MEMBERS ---
async def list_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    loading = await update.message.reply_text(strings.get('ADMIN_SEARCHING', lang))
    
    try:
        members = await run_db_call(db.get_members, limit=30) # Safe limit for message size
        
        if not members:
            await loading.edit_text(strings.get('ADMIN_LIST_EMPTY', lang), parse_mode="Markdown")
        else:
            items = []
            def esc(t): return str(t).replace('_', '\\_').replace('*', '\\*').replace('`', '\\`').replace('[', '\\[')
            for i, row in enumerate(members, 1):
                # row[2]=Name, row[3]=Matric
                name = row[2] if len(row) > 2 else "Unknown"
                matric = row[3] if len(row) > 3 else "Unknown"
                items.append(f"{i}. *{esc(name)}* (`{esc(matric)}`)")
            
            msg_text = strings.get('ADMIN_LIST_HEADER', lang).format(limit=len(members), items="\n\n".join(items))
            await loading.edit_text(msg_text, parse_mode="Markdown")

    except Exception as e:
        logger.error(e)
        await loading.edit_text(strings.get('ERR_DB_CONNECTION', lang))

    return states.ADMIN_MANAGE

# --- SEARCH MEMBERS ---
async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    await update.message.reply_text(
        strings.get('ADMIN_SEARCH_MODE_PROMPT', lang), 
        parse_mode="Markdown", 
        reply_markup=keyboards.get_search_mode_menu(lang)
    )
    return states.SEARCH_MODE

async def receive_search_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    text = update.message.text.strip()
    
    if text in strings.get_all('BTN_CANCEL') or text == "CANCEL": 
        return await back_to_manage(update, context)

    # Determine mode
    mode = "simple"
    if text in strings.get_all('BTN_SEARCH_DETAIL'):
        mode = "detail"
    elif text in strings.get_all('BTN_SEARCH_SIMPLE'):
        mode = "simple"
    else:
        # Invalid selection? Just default to simple or ask again.
        # Let's ask again for robustness
        await update.message.reply_text(
            strings.get('ADMIN_SEARCH_MODE_PROMPT', lang), 
            reply_markup=keyboards.get_search_mode_menu(lang)
        )
        return states.SEARCH_MODE
        
    context.user_data['search_mode'] = mode
    
    await update.message.reply_text(
        strings.get('ADMIN_SEARCH_PROMPT', lang),
        parse_mode="Markdown",
        reply_markup=keyboards.get_cancel_menu(lang)
    )
    return states.SEARCH_QUERY

async def search_perform(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    query = update.message.text.strip()
    mode = context.user_data.get('search_mode', 'simple')
    
    if query in strings.get_all('BTN_CANCEL') or query == "CANCEL": 
        return await back_to_manage(update, context)

    loading = await update.message.reply_text(strings.get('ADMIN_SEARCHING', lang))

    try:
        results = await run_db_call(db.search_members, query)
        
        if not results:
            await loading.edit_text(strings.get('ADMIN_SEARCH_EMPTY', lang).format(query=query), parse_mode="Markdown")
        else:
            items = []
            detail_cards = []
            limit = 20 if mode == 'simple' else 5
            
            for i, row in enumerate(results[:limit], 1):
                # row indexes: A=0, B=1, ...
                # C=2 (Name), D=3 (Matric), E=4 (Prog), I=8 (USAS Email), J=9 (IC), N=13 (Date), P=15 (ID), Q=16 (Receipt), R=17 (Status)
                
                name = row[2] if len(row) > 2 else "-"
                matric = row[3] if len(row) > 3 else "-"
                
                if mode == 'simple':
                    prog = strings.format_program_short(row[4] if len(row) > 4 else "-")
                    mem_id = row[15] if len(row) > 15 else "-" # P=15 is Membership ID
                    
                    # Local escape helper (duplicated for scope safety or move it up - moving it up is better but hard with replace tool constraints)
                    # Use simple replace here since function is defined lower down
                    def esc(t): return str(t).replace('_', '\\_').replace('*', '\\*').replace('`', '\\`').replace('[', '\\[')

                    simple_card = (
                        f"{i}.\n"
                        f"🔑 ID: `{esc(mem_id)}`\n"
                        f"👤 *{esc(name)}*\n"
                        f"🆔 `{esc(matric)}`\n"
                        f"🎓 {esc(prog)}"
                    )
                    items.append(simple_card)
                else:

                    def escape_md(text):
                        """Escape special characters for Telegram Markdown (Legacy)"""
                        return str(text).replace('_', '\\_').replace('*', '\\*').replace('`', '\\`').replace('[', '\\[')

                    def safe_get(idx): return escape_md(row[idx] if len(row) > idx else "-")
                    prog_detail = escape_md(strings.format_program_short(row[4] if len(row) > 4 else "-"))
                    
                    # Special handler for Receipt URL (Col S - Index 18)
                    raw_receipt = row[18] if len(row) > 18 else "-"
                    receipt_display = f"[Download PDF]({raw_receipt})" if raw_receipt.startswith("http") else escape_md(raw_receipt)

                    # Special handler for Proof URL (Col Q - Index 16)
                    # Convert drive 'open' links to 'download' links for better UX
                    raw_proof = row[16] if len(row) > 16 else "-"
                    if "drive.google.com" in raw_proof and "id=" in raw_proof:
                        raw_proof = raw_proof.replace("open?", "uc?export=download&")
                    
                    proof_display = f"[Proof PDF]({raw_proof})" if raw_proof.startswith("http") else escape_md(raw_proof)

                    detail_card = (
                        f"👤 *{safe_get(2)}*\n" # C Name
                        f"🆔 `{safe_get(3)}`\n" # D Matric
                        f"🎓 Prog: {prog_detail} | Sem: {safe_get(5)}\n" # E, F
                        f"📞 {safe_get(6)}\n" # G Phone
                        f"📧 {safe_get(7)}\n" # H Personal Email
                        f"🏫 {safe_get(8)}\n" # I USAS Email
                        f"🪪 IC: {safe_get(9)}\n" # J IC
                        f"🎂 {safe_get(10)} ({safe_get(11)})\n" # K Birthday, L Place
                        f"🏠 {safe_get(12)}\n" # M Address
                        f"📅 Entry: {safe_get(13)}\n" # N Date Entry
                        f"⏱️ Min: {safe_get(14)}\n" # O Minute
                        f"🔑 ID: `{safe_get(15)}`\n" # P Membership ID
                        f"📄 Proof: {proof_display}\n" # Q Receipt Proof (Index 16)
                        f"🧾 Invoice: `{safe_get(19)}`\n" # T Invoice No (Index 19)
                        f"📎 Receipt: {receipt_display}\n" # S Receipt URL (Index 18)
                        f"✅ Status: {safe_get(17)}\n" # R Status
                    )
                    items.append(detail_card)

                    _, row_idx = await run_db_call(db.find_member, str(matric).strip().upper())
                    detail_cards.append({
                        "text": detail_card,
                        "row_idx": row_idx,
                        "matric": str(matric).strip().upper(),
                        "show_renew": _is_row_expired(row),
                    })

            if mode == 'simple':
                msg_text = strings.get('ADMIN_SEARCH_RESULT', lang).format(mode=mode.upper(), query=query, items="\n\n".join(items))
                await loading.edit_text(msg_text, parse_mode="Markdown")
            else:
                msg_text = strings.get('ADMIN_SEARCH_RESULT', lang).format(
                    mode=mode.upper(),
                    query=query,
                    items=f"{len(detail_cards)} detailed card(s) below.",
                )
                await loading.edit_text(msg_text, parse_mode="Markdown")
                for card in detail_cards:
                    reply_markup = None
                    if card["show_renew"] and card["row_idx"]:
                        reply_markup = keyboards.get_admin_renew_keyboard(card["row_idx"], card["matric"], lang)
                    await update.message.reply_text(
                        card["text"],
                        parse_mode="Markdown",
                        reply_markup=reply_markup
                    )

    except Exception as e:
        logger.error(e)
        await loading.edit_text(strings.get('ERR_DB_CONNECTION', lang))
    
    await update.message.reply_text(strings.get('BTN_ADMIN_MANAGE', lang), reply_markup=keyboards.get_admin_manage_menu(lang))
    return states.ADMIN_MANAGE



# --- DELETE MEMBER FLOW ---
async def del_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    await update.message.reply_text(strings.get('ADMIN_DEL_START', lang), parse_mode="Markdown", reply_markup=keyboards.get_cancel_menu(lang))
    return states.DEL_MATRIC

async def del_matric(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    text = update.message.text.strip().upper()
    if text in strings.get_all('BTN_CANCEL') or text == "CANCEL": return await back_to_manage(update, context)
    
    loading = await update.message.reply_text(strings.get('ADMIN_SEARCHING', lang), parse_mode="Markdown")
    
    try:
        success, row = await run_db_call(db.delete_member, text)
        if success:
            db.log_action(update.effective_user.first_name, "DELETE_MEMBER", f"Matric: {text} (Row {row})")
            await loading.edit_text(strings.get('ADMIN_DEL_SUCCESS', lang).format(row=row), parse_mode="Markdown")
        else:
            await loading.edit_text(strings.get('ADMIN_DEL_NOT_FOUND', lang), parse_mode="Markdown")
    except Exception as e:
        logger.error(e)
        await loading.edit_text(strings.get('ERR_DB_CONNECTION', lang), parse_mode="Markdown")
        
    await update.message.reply_text(strings.get('BTN_ADMIN_MANAGE', lang), reply_markup=keyboards.get_admin_manage_menu(lang))
    return states.ADMIN_MANAGE

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    await update.message.reply_text(strings.get('ERR_CANCEL', lang), reply_markup=keyboards.get_admin_menu(lang))
    return states.ADMIN_MENU

# --- BROADCAST FLOW ---
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    await update.message.reply_text(
        strings.get('ADMIN_BROADCAST_PROMPT', lang), 
        parse_mode="Markdown", 
        reply_markup=keyboards.get_cancel_menu(lang)
    )
    return states.BROADCAST_MSG

async def broadcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    text = update.message.text
    
    if text in strings.get_all('BTN_CANCEL') or text == "CANCEL": 
        return await back(update, context)

    context.user_data['broadcast_msg'] = text
    
    # Get user count preview
    users = await run_db_call(db.get_all_users)
    count = len(users)
    
    await update.message.reply_text(
        strings.get('ADMIN_BROADCAST_CONFIRM', lang).format(msg=text, count=count),
        parse_mode="Markdown",
        reply_markup=keyboards.get_confirm_menu(lang)
    )
    return states.BROADCAST_CONFIRM

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    text = update.message.text
    
    if text in strings.get_all('BTN_CONFIRM_NO'):
        return await back(update, context)
        
    if text not in strings.get_all('BTN_CONFIRM_YES'):
        # Invalid input, ask again or cancel? Let's assume cancel or re-ask.
        # Simplest: cancel
        return await back(update, context)

    msg = context.user_data.get('broadcast_msg')
    if not msg: return await back(update, context)

    status_msg = await update.message.reply_text(strings.get('ADMIN_BROADCAST_START', lang))
    
    users = await run_db_call(db.get_all_users)
    success = 0
    failed = 0
    
    final_msg = strings.get('BROADCAST_TITLE', lang).format(msg=msg)
    
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=final_msg, parse_mode="Markdown")
            success += 1
        except Exception:
            failed += 1
            
    await status_msg.edit_text(
        strings.get('ADMIN_BROADCAST_DONE', lang).format(success=success, failed=failed), 
        parse_mode="Markdown"
    )
    
    db.log_action(update.effective_user.first_name, "BROADCAST", f"Msg: {msg[:30]}... | Success: {success}/{len(users)}")
    
    await update.message.reply_text(strings.get('ADMIN_DASHBOARD', lang), reply_markup=keyboards.get_admin_menu(lang), parse_mode="Markdown")
    return states.ADMIN_MENU

async def exit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context)
    await update.message.reply_text(strings.get('ADMIN_EXIT', lang), reply_markup=keyboards.get_main_menu(lang))
    return ConversationHandler.END


