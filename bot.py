import asyncio
import base64
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
import stats_web

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
WEBHOOK_ERROR_ALERT_MAX_AGE_SECONDS = int(
    os.getenv("WEBHOOK_ERROR_ALERT_MAX_AGE_SECONDS", "300")
)


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

                    last_error_message = str(
                        getattr(info, "last_error_message", "") or ""
                    ).strip()
                    raw_last_error_date = getattr(info, "last_error_date", 0)
                    if isinstance(raw_last_error_date, datetime.datetime):
                        if raw_last_error_date.tzinfo is None:
                            raw_last_error_date = raw_last_error_date.replace(
                                tzinfo=datetime.timezone.utc
                            )
                        last_error_date = int(raw_last_error_date.timestamp())
                    else:
                        last_error_date = int(raw_last_error_date or 0)
                    if last_error_message:
                        now_utc_ts = int(
                            datetime.datetime.now(datetime.timezone.utc).timestamp()
                        )
                        error_age_seconds = (
                            now_utc_ts - last_error_date if last_error_date > 0 else None
                        )
                        is_recent_error = (
                            error_age_seconds is not None
                            and 0 <= error_age_seconds <= WEBHOOK_ERROR_ALERT_MAX_AGE_SECONDS
                        )
                        if is_recent_error:
                            webhook_issues.append(
                                f"Last error: {last_error_message[:120]}"
                            )
                        else:
                            logger.info(
                                "Ignoring stale webhook last_error_message (age=%ss): %s",
                                error_age_seconds,
                                last_error_message[:120],
                            )

                    if webhook_issues:
                        await send_superadmin_alert(
                            application.bot,
                            "webhook_health_issue",
                            (
                                "*Webhook Health Alert*\n"
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
                            "*Webhook Health Check Failed*\n"
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
                        "*Sheets/API Error*\nCould not access `Registrations` sheet.",
                        cooldown_seconds=900,
                    )
            except Exception as e:
                logger.error("Sheets connectivity check failed: %s", e)
                await send_superadmin_alert(
                    application.bot,
                    "sheets_connectivity_check_error",
                    (
                        "*Sheets/API Check Failed*\n"
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
    filter_admin_stats_registration = build_filter("BTN_ADMIN_STATS_REGISTRATION")
    filter_admin_stats_demographic = build_filter("BTN_ADMIN_STATS_DEMOGRAPHIC")
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
            states.ADMIN_STATS_MENU: [
                MessageHandler(filter_admin_stats_registration, admin.stats_registration),
                MessageHandler(filter_admin_stats_demographic, admin.stats_demographic),
                MessageHandler(filter_back, admin.back_to_admin),
                CommandHandler("admin", admin.back_to_admin),
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
        CallbackQueryHandler(admin.stats_registration_full_callback, pattern="^admin_stats_reg_full$")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.review_accept_callback, pattern="^review_accept:")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.review_reject_callback, pattern="^review_reject:")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.review_renew_callback, pattern="^review_renew:")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.review_do_accept_callback, pattern="^review_do_accept:")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.review_do_reject_callback, pattern="^review_do_reject:")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.review_do_renew_callback, pattern="^review_do_renew:")
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

    async def demographic_report(request):
        token = request.match_info.get("token", "").strip()
        payload, err = stats_web.read_demographic_report(token)
        if err or not payload:
            return web.Response(status=404, text="Report link is invalid or expired.")

        import json
        course = payload.get("course_distribution", [])
        birth = payload.get("birth_year_distribution", [])
        stats_month_year = str(payload.get("stats_month_year", "-"))
        generated_at = str(payload.get("generated_at", "-"))
        total = int(payload.get("demographic_total", 0))

        course_labels = [str(item.get("label", "Unknown")) for item in course]
        course_vals = [float(item.get("pct", 0.0)) for item in course]
        birth_labels = [str(item.get("label", "Unknown")) for item in birth]
        birth_vals = [float(item.get("pct", 0.0)) for item in birth]
        favicon_tag = ""
        logo_path = os.path.join(os.path.dirname(__file__), "logostem.png")
        with suppress(Exception):
            with open(logo_path, "rb") as logo_file:
                logo_b64 = base64.b64encode(logo_file.read()).decode("ascii")
                favicon_tag = (
                    '<link rel="icon" type="image/png" '
                    f'href="data:image/png;base64,{logo_b64}" />'
                )

        html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Demographic Report</title>
  {favicon_tag}
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {{
      --stem-blue: #213e80;
      --stem-gold: #cc912b;
      --bg: #0b1325;
      --panel: #111c34;
      --line: #22314f;
      --text: #e2e8f0;
      --muted: #94a3b8;
      --shadow-soft: 0 10px 28px rgba(2, 6, 23, 0.4);
      --chip-primary-bg: rgba(90, 137, 250, 0.16);
      --chip-primary-border: rgba(90, 137, 250, 0.32);
      --chip-primary-text: #dbeafe;
      --chip-accent-bg: rgba(204, 145, 43, 0.18);
      --chip-accent-border: rgba(204, 145, 43, 0.45);
      --chip-accent-text: #f1c77f;
      --chip-bg: #172643;
      --chip-text: #d4def2;
      --hero-top: rgba(17, 28, 52, 0.95);
      --hero-bottom: rgba(17, 28, 52, 0.9);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--text);
      font-family: "Inter", "Segoe UI", Arial, sans-serif;
      background:
        radial-gradient(900px 420px at 100% -12%, rgba(33, 62, 128, 0.1), transparent 65%),
        radial-gradient(900px 420px at -8% 0%, rgba(204, 145, 43, 0.08), transparent 62%),
        var(--bg);
      min-height: 100vh;
      transition: background 0.25s ease, color 0.25s ease;
    }}
    .wrap {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 28px 18px 40px;
    }}
    .hero {{
      border: 1px solid var(--line);
      background:
        linear-gradient(160deg, var(--hero-top), var(--hero-bottom)),
        linear-gradient(120deg, rgba(33, 62, 128, 0.06), rgba(204, 145, 43, 0.06));
      border-radius: 18px;
      box-shadow: var(--shadow-soft);
      padding: 22px;
      margin-bottom: 14px;
    }}
    .hero h1 {{
      margin: 0 0 8px;
      font-size: clamp(24px, 4vw, 34px);
      line-height: 1.05;
      letter-spacing: -0.02em;
      font-weight: 800;
    }}
    .hero .sub {{
      color: var(--muted);
      font-size: 14px;
      line-height: 1.45;
      max-width: 760px;
    }}
    .chips {{
      margin-top: 16px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .chip {{
      padding: 8px 11px;
      border-radius: 10px;
      border: 1px solid var(--line);
      background: var(--chip-bg);
      font-size: 13px;
      color: var(--chip-text);
      font-weight: 500;
    }}
    .chip.primary {{
      border-color: var(--chip-primary-border);
      color: var(--chip-primary-text);
      background: var(--chip-primary-bg);
    }}
    .chip.accent {{
      border-color: var(--chip-accent-border);
      color: var(--chip-accent-text);
      background: var(--chip-accent-bg);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }}
    .card {{
      border-radius: 16px;
      background: var(--panel);
      border: 1px solid var(--line);
      box-shadow: var(--shadow-soft);
      padding: 16px;
    }}
    .card h3 {{
      margin: 0;
      font-size: 17px;
      letter-spacing: -0.01em;
      font-weight: 700;
    }}
    .muted {{
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
    }}
    .chart-box {{
      margin-top: 12px;
      height: 380px;
      position: relative;
    }}
    canvas {{ width: 100% !important; height: 100% !important; }}
    @media (max-width: 920px) {{
      .grid {{ grid-template-columns: 1fr; }}
      .chart-box {{ height: 340px; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>Demographic Dashboard</h1>
      <div class="sub">Interactive membership demographic overview with breakdown by course and year of birth.</div>
      <div class="chips">
        <div class="chip primary">Period: {stats_month_year}</div>
        <div class="chip accent">Total Members: {total}</div>
        <div class="chip">Generated: {generated_at}</div>
      </div>
    </section>
    <section class="grid">
      <article class="card">
        <h3>Course Distribution</h3>
        <div class="muted">Percentage share by program.</div>
        <div class="chart-box"><canvas id="courseChart"></canvas></div>
      </article>
      <article class="card">
        <h3>Year of Birth Distribution</h3>
        <div class="muted">Percentage share by birth year.</div>
        <div class="chart-box"><canvas id="birthChart"></canvas></div>
      </article>
    </section>
  </div>
  <script>
    const courseLabels = {json.dumps(course_labels)};
    const courseValues = {json.dumps(course_vals)};
    const birthLabels = {json.dumps(birth_labels)};
    const birthValues = {json.dumps(birth_vals)};

    const RAINBOW_PALETTE = [
      '#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#a855f7', '#06b6d4',
      '#84cc16', '#f97316', '#ec4899', '#6366f1', '#14b8a6', '#eab308'
    ];

    const CHART_THEME = {{
      palette: RAINBOW_PALETTE,
      sliceBorder: '#111c34',
      legendColor: '#dbe7ff',
      tooltipBg: 'rgba(15, 23, 42, 0.95)',
      centerColor: '#e2e8f0',
      centerSubColor: '#94a3b8',
    }};

    const centerTextPlugin = {{
      id: 'centerTextPlugin',
      beforeDraw(chart) {{
        const cfg = chart.options.plugins.centerText || {{}};
        if (!cfg.text) return;
        const meta = chart.getDatasetMeta(0);
        if (!meta || !meta.data || !meta.data.length) return;
        const arc = meta.data[0];
        const x = arc.x;
        const y = arc.y;
        const ctx = chart.ctx;
        const centerColor = cfg.color || '#0f172a';
        const centerSubColor = cfg.subColor || '#64748b';
        ctx.save();
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = centerColor;
        ctx.font = '700 26px Inter';
        ctx.fillText(String(cfg.text), x, y - 6);
        ctx.fillStyle = centerSubColor;
        ctx.font = '500 12px Inter';
        ctx.fillText('segments', x, y + 16);
        ctx.restore();
      }}
    }};

    const makeChart = (el, labels, values, themeConfig) => {{
      return new Chart(el, {{
        type: 'doughnut',
        data: {{
          labels,
          datasets: [{{
            data: values,
            backgroundColor: labels.map((_, i) => themeConfig.palette[i % themeConfig.palette.length]),
            borderColor: themeConfig.sliceBorder,
            borderWidth: 3,
            hoverOffset: 14
          }}]
        }},
        options: {{
          maintainAspectRatio: false,
          cutout: '63%',
          animation: {{
            animateRotate: true,
            duration: 1000,
            easing: 'easeOutQuart'
          }},
          plugins: {{
            centerText: {{
              text: labels.length,
              color: themeConfig.centerColor,
              subColor: themeConfig.centerSubColor
            }},
            legend: {{
              position: 'bottom',
              labels: {{
                usePointStyle: true,
                pointStyle: 'circle',
                boxWidth: 10,
                boxHeight: 10,
                padding: 14,
                color: themeConfig.legendColor,
                font: {{ family: 'Inter', size: 12, weight: 500 }}
              }}
            }},
            tooltip: {{
              backgroundColor: themeConfig.tooltipBg,
              padding: 10,
              titleFont: {{ family: 'Inter', size: 12, weight: 700 }},
              bodyFont: {{ family: 'Inter', size: 12, weight: 500 }},
              callbacks: {{
                label: (ctx) => ctx.label + ': ' + ctx.formattedValue + '%'
              }}
            }}
          }}
        }},
        plugins: [centerTextPlugin]
      }});
    }};

    const courseChart = makeChart(
      document.getElementById('courseChart'),
      courseLabels,
      courseValues,
      CHART_THEME
    );
    const birthChart = makeChart(
      document.getElementById('birthChart'),
      birthLabels,
      birthValues,
      CHART_THEME
    );
  </script>
</body>
</html>"""
        return web.Response(text=html, content_type="text/html")

    async def membership_profile_report(request):
        token = request.match_info.get("token", "").strip()
        payload, err = stats_web.read_member_profile_report(token)
        if err or not payload:
            return web.Response(status=404, text="Profile link is invalid or expired.")

        import html as html_lib

        def esc(value):
            return html_lib.escape(str(value if value is not None else "-"), quote=True)

        membership_id = esc(payload.get("membership_id", "-"))
        name = esc(payload.get("name", "-"))
        matric = esc(payload.get("matric", "-"))
        program = esc(payload.get("program", "-"))
        register_date = esc(payload.get("register_date", "-"))
        expired_date = esc(payload.get("expired_date", "-"))
        generated_at = esc(payload.get("generated_at", "-"))
        status_raw = str(payload.get("status", "Verified")).strip().lower()
        if "expired" in status_raw:
            badge_class = "expired"
            badge_text = "EXPIRED"
        elif "pending" in status_raw:
            badge_class = "pending"
            badge_text = "PENDING"
        else:
            badge_class = "verified"
            badge_text = "VERIFIED"

        favicon_tag = ""
        logo_src = ""
        logo_path = os.path.join(os.path.dirname(__file__), "logostem.png")
        with suppress(Exception):
            with open(logo_path, "rb") as logo_file:
                logo_b64 = base64.b64encode(logo_file.read()).decode("ascii")
                logo_src = f"data:image/png;base64,{logo_b64}"
                favicon_tag = (
                    '<link rel="icon" type="image/png" '
                    f'href="{logo_src}" />'
                )

        html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>STEM Membership Profile</title>
  {favicon_tag}
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {{
      --text: #eef4ff;
      --muted: #c9d7f2;
      --line: rgba(255, 235, 191, 0.45);
      --shadow: 0 18px 44px rgba(0, 0, 0, 0.55);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: #000;
      color: var(--text);
      font-family: "Inter", "Segoe UI", Arial, sans-serif;
      min-height: 100vh;
      padding: 22px 14px;
    }}
    .wrap {{
      max-width: 920px;
      margin: 0 auto;
      min-height: calc(100vh - 44px);
      display: grid;
      place-items: center;
    }}
    .card {{
      width: min(100%, 700px);
      aspect-ratio: 1.586;
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: var(--shadow);
      position: relative;
      overflow: hidden;
      isolation: isolate;
      transform-style: preserve-3d;
      transition: transform 0.16s ease;
      display: flex;
      flex-direction: column;
      padding: 16px 18px;
      background:
        radial-gradient(520px 320px at var(--gx1, 20%) var(--gy1, 20%), rgba(33, 62, 128, 0.95), transparent 66%),
        radial-gradient(520px 320px at var(--gx2, 80%) var(--gy2, 75%), rgba(204, 145, 43, 0.8), transparent 68%),
        linear-gradient(140deg, #203f82 0%, #17336d 42%, #cc912b 100%);
    }}
    .card::after {{
      content: "";
      position: absolute;
      inset: 0;
      z-index: -1;
      background:
        linear-gradient(118deg, rgba(255, 255, 255, 0.18) 8%, rgba(255, 255, 255, 0.03) 36%, transparent 62%);
      pointer-events: none;
    }}
    .top {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .logo {{
      width: 44px;
      height: 44px;
      border-radius: 10px;
      object-fit: cover;
      border: 1px solid rgba(255, 235, 191, 0.5);
      background: rgba(255, 255, 255, 0.14);
    }}
    .brand-name {{
      margin: 0;
      font-size: 15px;
      font-weight: 800;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: #fff7df;
    }}
    .badge {{
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 11px;
      font-weight: 700;
      white-space: nowrap;
      border: 1px solid transparent;
    }}
    .badge.verified {{
      border-color: rgba(34, 197, 94, 0.55);
      background: rgba(34, 197, 94, 0.22);
      color: #bbf7d0;
    }}
    .badge.pending {{
      border-color: rgba(250, 204, 21, 0.58);
      background: rgba(250, 204, 21, 0.24);
      color: #fef08a;
    }}
    .badge.expired {{
      border-color: rgba(239, 68, 68, 0.58);
      background: rgba(239, 68, 68, 0.24);
      color: #fecaca;
    }}
    .chip {{
      margin-top: 16px;
      width: 52px;
      height: 38px;
      border-radius: 10px;
      border: 1px solid rgba(255, 241, 209, 0.5);
      background:
        linear-gradient(135deg, rgba(255, 214, 131, 0.78), rgba(177, 124, 25, 0.85));
    }}
    .id-row {{
      margin-top: 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }}
    .id-label {{
      color: var(--muted);
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      margin-bottom: 6px;
      font-weight: 600;
    }}
    .id {{
      font-size: clamp(15px, 2.4vw, 19px);
      font-weight: 700;
      letter-spacing: 0.06em;
      color: #fef7e2;
      text-shadow: 0 1px 10px rgba(0, 0, 0, 0.3);
      overflow-wrap: anywhere;
    }}
    .btn {{
      border: 1px solid rgba(255, 235, 191, 0.5);
      background: rgba(255, 255, 255, 0.12);
      color: #fff3d1;
      border-radius: 10px;
      padding: 8px 10px;
      font-family: inherit;
      font-size: 12px;
      font-weight: 700;
      cursor: pointer;
      transition: filter 0.2s ease, background 0.2s ease;
      flex-shrink: 0;
    }}
    .btn:hover {{ filter: brightness(1.08); background: rgba(255, 255, 255, 0.18); }}
    .bottom {{
      margin-top: auto;
      border-top: 1px dashed rgba(255, 235, 191, 0.34);
      padding-top: 12px;
      display: grid;
      grid-template-columns: 1.35fr 1fr 1fr;
      gap: 10px 14px;
      align-items: end;
    }}
    .field .label {{
      color: var(--muted);
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.11em;
      margin-bottom: 4px;
      font-weight: 600;
    }}
    .field .value {{
      color: #f8fbff;
      font-size: 14px;
      font-weight: 700;
      line-height: 1.3;
      overflow-wrap: anywhere;
    }}
    .meta {{
      margin-top: 10px;
      color: #cfdbf6;
      font-size: 11px;
      display: flex;
      justify-content: space-between;
      gap: 10px;
      flex-wrap: wrap;
    }}
    #confettiCanvas {{
      position: fixed;
      inset: 0;
      width: 100vw;
      height: 100vh;
      pointer-events: none;
      z-index: 20;
    }}
    .toast {{
      position: fixed;
      right: 14px;
      bottom: 14px;
      border: 1px solid rgba(204, 145, 43, 0.45);
      background: rgba(204, 145, 43, 0.24);
      color: #fde7ba;
      border-radius: 10px;
      padding: 10px 12px;
      font-size: 12px;
      font-weight: 700;
      opacity: 0;
      transform: translateY(6px);
      transition: 0.2s ease;
    }}
    .toast.show {{ opacity: 1; transform: translateY(0); }}
    @media (max-width: 760px) {{
      .card {{
        width: min(100%, 420px);
        aspect-ratio: 0.95;
        padding: 14px;
      }}
      .bottom {{
        grid-template-columns: 1fr 1fr;
      }}
      .field.full-mobile {{ grid-column: 1 / -1; }}
      .id-row {{ flex-direction: column; align-items: flex-start; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <article class="card" id="profileCard">
      <section class="top">
        <div class="brand">
          <img class="logo" src="{logo_src}" alt="STEM Logo" />
          <h1 class="brand-name">STEM Membership</h1>
        </div>
        <div class="badge {badge_class}">{badge_text}</div>
      </section>

      <div class="chip" aria-hidden="true"></div>

      <section class="id-row">
        <div>
          <div class="id-label">Membership ID</div>
          <div class="id">{membership_id}</div>
        </div>
        <button class="btn" id="copyIdBtn" type="button">Copy ID</button>
      </section>

      <section class="bottom">
        <div class="field full-mobile">
          <div class="label">Cardholder Name</div>
          <div class="value">{name}</div>
        </div>
        <div class="field">
          <div class="label">Matric</div>
          <div class="value">{matric}</div>
        </div>
        <div class="field">
          <div class="label">Program</div>
          <div class="value">{program}</div>
        </div>
        <div class="field">
          <div class="label">Register Date</div>
          <div class="value">{register_date}</div>
        </div>
        <div class="field">
          <div class="label">Expired Date</div>
          <div class="value">{expired_date}</div>
        </div>
      </section>

      <div class="meta">
        <span>Generated: {generated_at} (Asia/Kuala Lumpur)</span>
        <span>Secure temporary profile link</span>
      </div>
    </article>
  </div>
  <canvas id="confettiCanvas"></canvas>
  <div class="toast" id="toast">Copied</div>
  <script>
    const membershipId = {membership_id!r};
    const confettiKey = {f"stem_profile_confetti_{token}"!r};
    const copyBtn = document.getElementById('copyIdBtn');
    const toast = document.getElementById('toast');
    const card = document.getElementById('profileCard');

    const showToast = (text) => {{
      toast.textContent = text;
      toast.classList.add('show');
      setTimeout(() => toast.classList.remove('show'), 1400);
    }};

    copyBtn.addEventListener('click', async () => {{
      try {{
        await navigator.clipboard.writeText(membershipId);
        showToast('Membership ID copied');
      }} catch {{
        showToast('Copy failed');
      }}
    }});

    const maxTilt = 3;
    card.addEventListener('mousemove', (e) => {{
      const rect = card.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width;
      const y = (e.clientY - rect.top) / rect.height;
      const rx = (0.5 - y) * maxTilt;
      const ry = (x - 0.5) * maxTilt;
      card.style.transform = 'perspective(1000px) rotateX(' + rx + 'deg) rotateY(' + ry + 'deg)';
    }});
    card.addEventListener('mouseleave', () => {{
      card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg)';
    }});

    let gT = 0;
    const gradientState = {{
      c1x: 20, c1y: 20, c2x: 80, c2y: 75,
      t1x: 20, t1y: 20, t2x: 80, t2y: 75,
    }};
    const nextTargets = () => {{
      gradientState.t1x = 10 + Math.random() * 28;
      gradientState.t1y = 10 + Math.random() * 34;
      gradientState.t2x = 62 + Math.random() * 28;
      gradientState.t2y = 58 + Math.random() * 32;
    }};
    nextTargets();
    const gradientTick = () => {{
      gT += 1;
      if (gT % 240 === 0) nextTargets();
      const lerp = 0.012;
      gradientState.c1x += (gradientState.t1x - gradientState.c1x) * lerp;
      gradientState.c1y += (gradientState.t1y - gradientState.c1y) * lerp;
      gradientState.c2x += (gradientState.t2x - gradientState.c2x) * lerp;
      gradientState.c2y += (gradientState.t2y - gradientState.c2y) * lerp;
      card.style.setProperty('--gx1', gradientState.c1x.toFixed(2) + '%');
      card.style.setProperty('--gy1', gradientState.c1y.toFixed(2) + '%');
      card.style.setProperty('--gx2', gradientState.c2x.toFixed(2) + '%');
      card.style.setProperty('--gy2', gradientState.c2y.toFixed(2) + '%');
      requestAnimationFrame(gradientTick);
    }};
    requestAnimationFrame(gradientTick);

    const runConfetti = () => {{
      const canvas = document.getElementById('confettiCanvas');
      const ctx = canvas.getContext('2d');
      const dpr = window.devicePixelRatio || 1;
      const resize = () => {{
        canvas.width = Math.floor(window.innerWidth * dpr);
        canvas.height = Math.floor(window.innerHeight * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      }};
      resize();
      window.addEventListener('resize', resize, {{ passive: true }});

      const pieces = Array.from({{ length: 120 }}, (_, i) => ({{
        x: Math.random() * window.innerWidth,
        y: -20 - Math.random() * window.innerHeight * 0.3,
        w: 6 + Math.random() * 8,
        h: 8 + Math.random() * 10,
        vy: 2 + Math.random() * 3.4,
        vx: -1.2 + Math.random() * 2.4,
        r: Math.random() * Math.PI,
        vr: -0.2 + Math.random() * 0.4,
        c: i % 2 ? '#cc912b' : '#213e80',
      }}));

      const start = performance.now();
      const duration = 2600;
      const tick = (t) => {{
        const elapsed = t - start;
        ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
        for (const p of pieces) {{
          p.x += p.vx;
          p.y += p.vy;
          p.r += p.vr;
          p.vy += 0.015;
          ctx.save();
          ctx.translate(p.x, p.y);
          ctx.rotate(p.r);
          ctx.fillStyle = p.c;
          ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
          ctx.restore();
        }}
        if (elapsed < duration) {{
          requestAnimationFrame(tick);
        }} else {{
          ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
          canvas.remove();
        }}
      }};
      requestAnimationFrame(tick);
    }};

    if (!localStorage.getItem(confettiKey)) {{
      runConfetti();
      localStorage.setItem(confettiKey, '1');
    }} else {{
      const canvas = document.getElementById('confettiCanvas');
      if (canvas) canvas.remove();
    }}
  </script>
</body>
</html>"""
        return web.Response(text=html, content_type="text/html")

    app = web.Application()
    app.router.add_post("/telegram", telegram_webhook)
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    app.router.add_get("/stats/demographic/{token}", demographic_report)
    app.router.add_get("/profile/membership/{token}", membership_profile_report)

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

