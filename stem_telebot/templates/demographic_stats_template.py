"""Demographic stats report HTML template."""

import json


def _to_js(value):
    return json.dumps(value).replace("</", "<\\/")


def render_demographic_report(
    *,
    favicon_tag: str,
    stats_month_year: str,
    generated_at: str,
    total: int,
    course_labels: list[str],
    course_vals: list[float],
    birth_labels: list[str],
    birth_vals: list[float],
) -> str:
    return f"""<!doctype html>
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
      --bg: #050a18;
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
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--bg);
      min-height: 100vh;
      padding: 24px 16px;
      transition: background 0.25s ease, color 0.25s ease;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      background:
        radial-gradient(ellipse 700px 500px at 20% 10%, rgba(33, 62, 128, 0.25), transparent),
        radial-gradient(ellipse 600px 400px at 80% 90%, rgba(204, 145, 43, 0.15), transparent);
      pointer-events: none;
      z-index: 0;
    }}
    .wrap {{
      width: min(1120px, 100%);
      margin: 0 auto;
      position: relative;
      z-index: 1;
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
    const courseLabels = {_to_js(course_labels)};
    const courseValues = {_to_js(course_vals)};
    const birthLabels = {_to_js(birth_labels)};
    const birthValues = {_to_js(birth_vals)};

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

    makeChart(
      document.getElementById('courseChart'),
      courseLabels,
      courseValues,
      CHART_THEME
    );
    makeChart(
      document.getElementById('birthChart'),
      birthLabels,
      birthValues,
      CHART_THEME
    );
  </script>
</body>
</html>"""
