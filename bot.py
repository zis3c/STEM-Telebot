import asyncio
import datetime
import hmac
import logging
import os
import re
from contextlib import suppress
from zoneinfo import ZoneInfo

from aiohttp import ClientSession, web
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import admin
import handlers
import states
import strings
import superadmin

# --- CONFIGURATION ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
PORT = int(os.getenv("PORT", 10000))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
KL_TZ = ZoneInfo("Asia/Kuala_Lumpur")


# --- SELF PINGER (KEEP ALIVE) ---
async def self_pinger():
    """Pings the bot's own URL every 14 minutes to prevent sleep."""
    while True:
        await asyncio.sleep(14 * 60)
        if WEBHOOK_URL:
            try:
                url = f"{WEBHOOK_URL}/health"
                async with ClientSession() as session:
                    async with session.get(url) as resp:
                        logger.info("Self-Ping status: %s", resp.status)
            except Exception as e:
                logger.error("Self-Ping failed: %s", e)


# --- MAINTENANCE LOOP (ROBUST SCHEDULING) ---
async def maintenance_loop(application):
    """Checks every 15 minutes and sends daily logs only after 8:00 AM KL."""
    from database import db
    from handlers import send_daily_logs, send_superadmin_alert, ALERT_WEBHOOK_PENDING_THRESHOLD

    while True:
        try:
            now_kl = datetime.datetime.now(KL_TZ)
            expected_webhook_url = f"{WEBHOOK_URL}/telegram" if WEBHOOK_URL else ""

            # Webhook and queue health checks should run all day, not only after 08:00.
            if WEBHOOK_URL:
                try:
                    info = await application.bot.get_webhook_info()
                    webhook_issues = []
                    if info.url != expected_webhook_url:
                        webhook_issues.append("Webhook URL mismatch.")
                    if info.pending_update_count >= ALERT_WEBHOOK_PENDING_THRESHOLD:
                        webhook_issues.append(
                            f"Pending updates high: {info.pending_update_count}."
                        )
                    if getattr(info, "last_error_message", ""):
                        webhook_issues.append(
                            f"Last error: {str(info.last_error_message)[:120]}"
                        )

                    if webhook_issues:
                        await send_superadmin_alert(
                            application.bot,
                            "webhook_health_issue",
                            (
                                "🚨 *Webhook Health Alert*\n"
                                + "\n".join(f"- {_}" for _ in webhook_issues)
                            ),
                            cooldown_seconds=900,
                        )
                except Exception as e:
                    logger.error("Webhook health check failed: %s", e)
                    await send_superadmin_alert(
                        application.bot,
                        "webhook_health_check_error",
                        (
                            "🚨 *Webhook Health Check Failed*\n"
                            f"Error: `{str(e)[:180]}`"
                        ),
                        cooldown_seconds=900,
                    )

            # Basic sheets connectivity check.
            try:
                sheet_ok = await asyncio.to_thread(db.get_sheet, "Registrations")
                if not sheet_ok:
                    await send_superadmin_alert(
                        application.bot,
                        "sheets_connectivity_issue",
                        "🚨 *Sheets/API Error*\nCould not access `Registrations` sheet.",
                        cooldown_seconds=900,
                    )
            except Exception as e:
                logger.error("Sheets connectivity check failed: %s", e)
                await send_superadmin_alert(
                    application.bot,
                    "sheets_connectivity_check_error",
                    (
                        "🚨 *Sheets/API Check Failed*\n"
                        f"Error: `{str(e)[:180]}`"
                    ),
                    cooldown_seconds=900,
                )

            # Only allow daily log dispatch from 08:00 onward (KL time).
            if now_kl.hour < 8:
                await asyncio.sleep(15 * 60)
                continue

            report_date = (now_kl.date() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            last_date = await asyncio.to_thread(db.get_last_maintenance)

            if report_date != last_date:
                logger.info(
                    "Daily log report due. Last run: %s, Target: %s",
                    last_date,
                    report_date,
                )

                class MockContext:
                    def __init__(self, bot):
                        self.bot = bot

                await send_daily_logs(MockContext(application.bot))
        except Exception as e:
            logger.error("Maintenance loop error: %s", e)

        await asyncio.sleep(15 * 60)


# --- HELPER FOR FILTERS ---
def build_filter(key):
    """Builds a Regex filter that matches ANY language variation of a button."""
    options = strings.get_all(key)
    pattern = "^(" + "|".join([re.escape(opt) for opt in options]) + ")$"
    return filters.Regex(pattern)


# --- WEBHOOK & MAIN ---
async def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN is missing.")

    application = ApplicationBuilder().token(TOKEN).build()

    # Dynamic Filters (Multi-Language)
    filter_check = build_filter("BTN_CHECK")
    filter_help = build_filter("BTN_HELP")
    filter_settings = build_filter("BTN_SETTINGS")
    filter_languages = build_filter("BTN_LANGUAGES")
    filter_become_member = build_filter("BTN_BECOME_MEMBER")

    filter_back = build_filter("BTN_BACK")
    filter_cancel = build_filter("BTN_CANCEL")
    filter_lang_en = build_filter("BTN_LANG_EN")
    filter_lang_ms = build_filter("BTN_LANG_MS")

    # Admin Filters
    filter_admin_manage = build_filter("BTN_ADMIN_MANAGE")
    filter_admin_del = build_filter("BTN_ADMIN_DEL")
    filter_admin_list = build_filter("BTN_ADMIN_LIST")
    filter_admin_search = build_filter("BTN_ADMIN_SEARCH")
    filter_admin_broadcast = build_filter("BTN_ADMIN_BROADCAST")
    filter_admin_stats = build_filter("BTN_ADMIN_STATS")
    filter_admin_check_pending = build_filter("BTN_ADMIN_CHECK_PENDING")
    filter_admin_exit = build_filter("BTN_ADMIN_EXIT")

    # Superadmin Filters
    filter_sa_maint = build_filter("BTN_SA_MAINTENANCE")
    filter_sa_admins = build_filter("BTN_SA_ADMINS")
    filter_sa_health = build_filter("BTN_SA_HEALTH")
    filter_sa_refresh = build_filter("BTN_SA_REFRESH")
    filter_sa_logs = build_filter("BTN_SA_LOGS")

    # Superadmin Sub-menu Filters
    filter_sa_add = build_filter("BTN_SA_ADD_ADMIN")
    filter_sa_list = build_filter("BTN_SA_LIST_ADMIN")
    filter_sa_del = build_filter("BTN_SA_DEL_ADMIN")
    filter_sa_exit = build_filter("BTN_SA_EXIT")

    # User Config
    user_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filter_check, handlers.check_start),
            MessageHandler(filter_settings, handlers.settings_menu),
            MessageHandler(filter_languages, handlers.languages_menu),
            MessageHandler(filter_become_member, handlers.registration_menu),
        ],
        states={
            states.ASK_MATRIC: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~filter_cancel,
                    handlers.receive_matric,
                )
            ],
            states.ASK_IC: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~filter_cancel,
                    handlers.receive_ic,
                )
            ],
        },
        fallbacks=[
            MessageHandler(filter_cancel | filters.COMMAND, handlers.cancel),
            MessageHandler(filter_settings, handlers.settings_menu),
            MessageHandler(filter_languages, handlers.languages_menu),
        ],
    )

    super_conv = ConversationHandler(
        entry_points=[CommandHandler("superadmin", superadmin.start)],
        states={
            states.SUPER_MENU: [
                MessageHandler(filter_sa_maint, superadmin.toggle_maintenance),
                MessageHandler(filter_sa_health, superadmin.check_health),
                MessageHandler(filter_sa_admins, superadmin.manage_admins),
                MessageHandler(filter_sa_refresh, superadmin.refresh_config),
                MessageHandler(filter_sa_logs, superadmin.view_logs),
                MessageHandler(filter_sa_exit, superadmin.exit),
            ],
            states.SUPER_ADMIN_MANAGE: [
                MessageHandler(filter_sa_add, superadmin.add_admin_start),
                MessageHandler(filter_sa_list, superadmin.list_admins),
                MessageHandler(filter_sa_del, superadmin.del_admin_start),
                MessageHandler(filter_back, superadmin.back_to_super),
                MessageHandler(filter_sa_exit, superadmin.exit),
            ],
            states.SUPER_ADD_ID: [
                MessageHandler(filter_cancel, superadmin.back_to_manage),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~filter_cancel,
                    superadmin.add_admin_save,
                ),
            ],
            states.SUPER_DEL_ID: [
                MessageHandler(filter_cancel, superadmin.back_to_manage),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~filter_cancel,
                    superadmin.del_admin_perform,
                ),
            ],
        },
        fallbacks=[CommandHandler("cancel", superadmin.exit)],
        allow_reentry=True,
    )

    # Admin Config
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("admin", admin.start)],
        states={
            states.ADMIN_MENU: [
                MessageHandler(filter_admin_manage, admin.manage_menu),
                MessageHandler(filter_admin_broadcast, admin.broadcast_start),
                MessageHandler(filter_admin_check_pending, admin.check_pending_click),
                MessageHandler(filter_admin_stats, admin.stats),
                MessageHandler(filter_admin_exit, admin.exit),
                CommandHandler("admin", admin.start),
            ],
            states.ADMIN_MANAGE: [
                MessageHandler(filter_admin_del, admin.del_start),
                MessageHandler(filter_admin_list, admin.list_members),
                MessageHandler(filter_admin_search, admin.search_start),
                MessageHandler(filter_back, admin.back_to_admin),
                CommandHandler("admin", admin.back_to_admin),
            ],
            states.DEL_MATRIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin.del_matric)
            ],
            states.SEARCH_MODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin.receive_search_mode)
            ],
            states.SEARCH_QUERY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin.search_perform)
            ],
            states.BROADCAST_MSG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin.broadcast_confirm)
            ],
            states.BROADCAST_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin.broadcast_send)
            ],
        },
        fallbacks=[CommandHandler("cancel", admin.exit)],
    )

    # General Handlers
    application.add_handler(super_conv)
    application.add_handler(admin_conv)
    application.add_handler(user_conv)
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CommandHandler("settings", handlers.settings_menu))
    application.add_handler(CommandHandler("check_pending", handlers.check_pending_now))

    application.add_handler(MessageHandler(filter_help, handlers.help_command))
    application.add_handler(MessageHandler(filter_settings, handlers.settings_menu))
    application.add_handler(MessageHandler(filter_languages, handlers.languages_menu))
    application.add_handler(MessageHandler(filter_become_member, handlers.registration_menu))

    application.add_handler(MessageHandler(filter_lang_en, handlers.set_lang_en))
    application.add_handler(MessageHandler(filter_lang_ms, handlers.set_lang_ms))
    application.add_handler(MessageHandler(filter_back, handlers.start))
    application.add_handler(
        CallbackQueryHandler(handlers.how_it_works_callback, pattern="^how_it_works$")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.help_back_callback, pattern="^help_back$")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.review_accept_callback, pattern="^review_accept:")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.review_reject_callback, pattern="^review_reject:")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.review_do_accept_callback, pattern="^review_do_accept:")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.review_do_reject_callback, pattern="^review_do_reject:")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.review_cancel_callback, pattern="^review_cancel:")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.review_detail_callback, pattern="^review_detail:")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.review_back_callback, pattern="^review_back:")
    )

    # Global Logger (Group -1) - Runs for EVERYTHING
    application.add_handler(MessageHandler(filters.ALL, handlers.log_any_update), group=-1)

    # Job Queue
    if application.job_queue:
        application.job_queue.run_repeating(
            handlers.check_registrations, interval=60, first=10
        )

    app_ready = asyncio.Event()
    background_tasks = []

    async def telegram_webhook(request):
        if not app_ready.is_set():
            return web.Response(status=503, text="Starting")

        try:
            if WEBHOOK_SECRET:
                recv_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
                if not hmac.compare_digest(recv_secret, WEBHOOK_SECRET):
                    logger.warning("Rejected webhook request with invalid secret token.")
                    return web.Response(status=403, text="Forbidden")

            update_data = await request.json()
            await application.process_update(Update.de_json(update_data, application.bot))
            return web.Response(text="OK")
        except Exception:
            logger.exception("Webhook processing error")
            return web.Response(status=500, text="Webhook error")

    async def health(request):
        status = "Alive" if app_ready.is_set() else "Starting"
        return web.Response(text=status)

    app = web.Application()
    app.router.add_post("/telegram", telegram_webhook)
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info("HTTP server started on port %s", PORT)

    try:
        await application.initialize()
        await application.start()

        if WEBHOOK_URL:
            if not WEBHOOK_SECRET:
                raise RuntimeError(
                    "WEBHOOK_URL is set but TELEGRAM_WEBHOOK_SECRET is missing. "
                    "Set TELEGRAM_WEBHOOK_SECRET to protect webhook authenticity."
                )
            webhook_path = f"{WEBHOOK_URL}/telegram"
            await application.bot.set_webhook(webhook_path, secret_token=WEBHOOK_SECRET)
            logger.info("Webhook configured: %s", webhook_path)
        else:
            logger.info("No WEBHOOK_URL found. Starting polling...")
            await application.bot.delete_webhook(drop_pending_updates=True)
            if application.updater:
                await application.updater.start_polling()

        from telegram import BotCommand

        commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Get help information"),
            BotCommand("settings", "Open Settings"),
        ]
        await application.bot.set_my_commands(commands)

        background_tasks.append(asyncio.create_task(self_pinger(), name="self_pinger"))
        background_tasks.append(
            asyncio.create_task(maintenance_loop(application), name="maintenance_loop")
        )
        app_ready.set()

        while True:
            await asyncio.sleep(3600)
    finally:
        app_ready.clear()

        for task in background_tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        with suppress(Exception):
            if application.updater:
                await application.updater.stop()
        with suppress(Exception):
            await application.stop()
        with suppress(Exception):
            await application.shutdown()
        with suppress(Exception):
            await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
