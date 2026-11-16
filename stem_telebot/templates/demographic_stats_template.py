"""Demographic and registration stats report HTML template with period filtering."""

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
    periods_data: dict | None = None,
    lang: str = "EN",
) -> str:
    is_ms = lang.upper() == "MS"

    # Fallback if periods_data is not provided
    if not periods_data:
        periods_data = {
            "all": {
                "label_en": "All Time",
                "label_ms": "Keseluruhan",
                "period_desc_en": stats_month_year,
                "period_desc_ms": stats_month_year,
                "total_applications": total,
                "approved": total,
                "pending": 0,
                "rejected": 0,
                "course_distribution": [
                    {"label": l, "count": 0, "pct": v} for l, v in zip(course_labels, course_vals)
                ],
                "birth_year_distribution": [
                    {"label": l, "count": 0, "pct": v} for l, v in zip(birth_labels, birth_vals)
                ],
                "members": [],
            }
        }

    # Desired order for options in dropdown
    filter_order = ["month", "today", "prev_month", "prev_year", "all"]
    default_period = "month" if "month" in periods_data else (filter_order[0] if filter_order[0] in periods_data else list(periods_data.keys())[0])

    # Text translations
    t = {
        "title": "Dashboard Statistik Keahlian" if is_ms else "Demographic & Stats Dashboard",
        "subtitle": (
            "Gambaran interaktif demografi dan permohonan keahlian mengikut kursus, tahun lahir, dan tempoh masa."
            if is_ms else
            "Interactive membership demographic and application overview by course, birth year, and time period."
        ),
        "filter_label": "Pilih Tempoh:" if is_ms else "Filter Period:",
        "period_prefix": "Tempoh: " if is_ms else "Period: ",
        "approved_prefix": "Ahli Lulus: " if is_ms else "Approved: ",
        "applications_prefix": "Permohonan: " if is_ms else "Applications: ",
        "pending_prefix": "Pending: " if is_ms else "Pending: ",
        "rejected_prefix": "Ditolak: " if is_ms else "Rejected: ",
        "generated_prefix": "Dijana: " if is_ms else "Generated: ",
        "course_title": "Taburan Kursus" if is_ms else "Course Distribution",
        "course_sub": "Peratusan ahli mengikut program pengajian." if is_ms else "Percentage share by academic program.",
        "birth_title": "Taburan Tahun Lahir" if is_ms else "Year of Birth Distribution",
        "birth_sub": "Peratusan ahli mengikut tahun kelahiran." if is_ms else "Percentage share by birth year.",
        "members_title": "Senarai Ahli Lulus" if is_ms else "Approved Members",
        "members_sub": "Ahli yang diluluskan pendaftaran dalam tempoh ini." if is_ms else "Approved members registered in this selected period.",
        "search_placeholder": "Cari nama ahli..." if is_ms else "Search member name...",
        "no_members": "Tiada pendaftaran diluluskan bagi tempoh ini." if is_ms else "No approved registrations for this period.",
        "no_data": "Tiada data" if is_ms else "No data",
        "segments": "segmen" if is_ms else "segments",
    }

    # Generate <option> tags
    options_html = []
    for key in filter_order:
        if key in periods_data:
            p = periods_data[key]
            lbl = p.get("period_desc_ms" if is_ms else "period_desc_en", p.get("label_ms" if is_ms else "label_en", key))
            sel = " selected" if key == default_period else ""
            options_html.append(f'<option value="{key}"{sel}>{lbl}</option>')

    # Any other keys not in filter_order
    for key, p in periods_data.items():
        if key not in filter_order:
            lbl = p.get("period_desc_ms" if is_ms else "period_desc_en", key)
            options_html.append(f'<option value="{key}">{lbl}</option>')

    options_rendered = "\n          ".join(options_html)

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{t["title"]}</title>
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
      --chip-pending-bg: rgba(245, 158, 11, 0.16);
      --chip-pending-border: rgba(245, 158, 11, 0.4);
      --chip-pending-text: #fcd34d;
      --chip-rejected-bg: rgba(239, 68, 68, 0.16);
      --chip-rejected-border: rgba(239, 68, 68, 0.4);
      --chip-rejected-text: #fca5a5;
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
      font-size: clamp(22px, 3.8vw, 32px);
      line-height: 1.1;
      letter-spacing: -0.02em;
      font-weight: 800;
    }}
    .hero .sub {{
      color: var(--muted);
      font-size: 14px;
      line-height: 1.45;
      max-width: 760px;
    }}
    .filter-bar {{
      margin-top: 18px;
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }}
    .filter-label {{
      font-size: 14px;
      font-weight: 600;
      color: var(--text);
    }}
    .filter-select {{
      background: var(--chip-bg);
      color: var(--text);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 9px 38px 9px 14px;
      font-size: 14px;
      font-weight: 600;
      font-family: inherit;
      cursor: pointer;
      appearance: none;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='%2394a3b8' viewBox='0 0 16 16'%3E%3Cpath d='M7.247 11.14 2.451 5.658C1.885 5.013 2.345 4 3.204 4h9.592a1 1 0 0 1 .753 1.659l-4.796 5.48a1 1 0 0 1-1.506 0z'/%3E%3C/svg%3E");
      background-repeat: no-repeat;
      background-position: right 14px center;
      transition: border-color 0.2s, box-shadow 0.2s;
    }}
    .filter-select:hover {{
      border-color: #3b82f6;
    }}
    .filter-select:focus {{
      outline: none;
      border-color: #3b82f6;
      box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.25);
    }}
    .chips {{
      margin-top: 14px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .chip {{
      padding: 7px 12px;
      border-radius: 10px;
      border: 1px solid var(--line);
      background: var(--chip-bg);
      font-size: 13px;
      color: var(--chip-text);
      font-weight: 500;
      transition: all 0.2s ease;
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
    .chip.pending {{
      border-color: var(--chip-pending-border);
      color: var(--chip-pending-text);
      background: var(--chip-pending-bg);
    }}
    .chip.rejected {{
      border-color: var(--chip-rejected-border);
      color: var(--chip-rejected-text);
      background: var(--chip-rejected-bg);
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

    /* Members list section */
    .members-section {{
      margin-top: 14px;
    }}
    .members-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 12px;
    }}
    .search-input {{
      background: var(--bg);
      color: var(--text);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 7px 12px;
      font-size: 13px;
      font-family: inherit;
      width: 240px;
      transition: border-color 0.2s;
    }}
    .search-input:focus {{
      outline: none;
      border-color: #3b82f6;
    }}
    .members-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 8px;
      max-height: 280px;
      overflow-y: auto;
      padding-right: 4px;
    }}
    .member-item {{
      background: rgba(5, 10, 24, 0.6);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px 12px;
      font-size: 13px;
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .member-num {{
      color: var(--muted);
      font-size: 11px;
      font-weight: 600;
      min-width: 22px;
    }}
    .member-name {{
      font-weight: 500;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .no-data-msg {{
      text-align: center;
      padding: 24px;
      color: var(--muted);
      font-size: 14px;
    }}

    @media (max-width: 920px) {{
      .grid {{ grid-template-columns: 1fr; }}
      .chart-box {{ height: 340px; }}
      .search-input {{ width: 100%; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>{t["title"]}</h1>
      <div class="sub">{t["subtitle"]}</div>

      <div class="filter-bar">
        <label for="periodSelect" class="filter-label">{t["filter_label"]}</label>
        <select id="periodSelect" class="filter-select">
          {options_rendered}
        </select>
      </div>

      <div class="chips">
        <div class="chip primary" id="chipPeriod">{t["period_prefix"]}...</div>
        <div class="chip accent" id="chipApproved">{t["approved_prefix"]}0</div>
        <div class="chip" id="chipApplications">{t["applications_prefix"]}0</div>
        <div class="chip pending" id="chipPending">{t["pending_prefix"]}0</div>
        <div class="chip rejected" id="chipRejected">{t["rejected_prefix"]}0</div>
        <div class="chip" id="chipGenerated">{t["generated_prefix"]}{generated_at}</div>
      </div>
    </section>

    <section class="grid">
      <article class="card">
        <h3>{t["course_title"]}</h3>
        <div class="muted">{t["course_sub"]}</div>
        <div class="chart-box"><canvas id="courseChart"></canvas></div>
      </article>
      <article class="card">
        <h3>{t["birth_title"]}</h3>
        <div class="muted">{t["birth_sub"]}</div>
        <div class="chart-box"><canvas id="birthChart"></canvas></div>
      </article>
    </section>

    <section class="card members-section">
      <div class="members-header">
        <div>
          <h3 id="membersHeaderTitle">{t["members_title"]} (<span id="membersCount">0</span>)</h3>
          <div class="muted">{t["members_sub"]}</div>
        </div>
        <input type="text" id="memberSearch" placeholder="{t["search_placeholder"]}" class="search-input" />
      </div>
      <div id="membersContainer"></div>
    </section>
  </div>

  <script>
    const periodsData = {_to_js(periods_data)};
    const isMs = {_to_js(is_ms)};
    const t = {_to_js(t)};

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
        if (!cfg.text && cfg.text !== 0) return;
        const meta = chart.getDatasetMeta(0);
        if (!meta || !meta.data || !meta.data.length) return;
        const arc = meta.data[0];
        const x = arc.x;
        const y = arc.y;
        const ctx = chart.ctx;
        const centerColor = cfg.color || '#e2e8f0';
        const centerSubColor = cfg.subColor || '#94a3b8';
        ctx.save();
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = centerColor;
        ctx.font = '700 24px Inter';
        ctx.fillText(String(cfg.text), x, y - 6);
        ctx.fillStyle = centerSubColor;
        ctx.font = '500 12px Inter';
        ctx.fillText(t.segments, x, y + 16);
        ctx.restore();
      }}
    }};

    const createDonutChart = (el) => {{
      return new Chart(el, {{
        type: 'doughnut',
        data: {{
          labels: [],
          datasets: [{{
            data: [],
            backgroundColor: [],
            borderColor: CHART_THEME.sliceBorder,
            borderWidth: 3,
            hoverOffset: 12
          }}]
        }},
        options: {{
          maintainAspectRatio: false,
          cutout: '63%',
          animation: {{
            animateRotate: true,
            duration: 750,
            easing: 'easeOutQuart'
          }},
          plugins: {{
            centerText: {{
              text: 0,
              color: CHART_THEME.centerColor,
              subColor: CHART_THEME.centerSubColor
            }},
            legend: {{
              position: 'bottom',
              labels: {{
                usePointStyle: true,
                pointStyle: 'circle',
                boxWidth: 9,
                boxHeight: 9,
                padding: 12,
                color: CHART_THEME.legendColor,
                font: {{ family: 'Inter', size: 12, weight: 500 }}
              }}
            }},
            tooltip: {{
              backgroundColor: CHART_THEME.tooltipBg,
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

    const courseChart = createDonutChart(document.getElementById('courseChart'));
    const birthChart = createDonutChart(document.getElementById('birthChart'));

    const escapeHtml = (text) => {{
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }};

    const renderMembersList = (members, query = '') => {{
      const container = document.getElementById('membersContainer');
      document.getElementById('membersCount').textContent = members.length;

      if (!members || members.length === 0) {{
        container.innerHTML = `<div class="no-data-msg">${{query ? (isMs ? 'Tiada nama yang sepadan.' : 'No matching members found.') : t.no_members}}</div>`;
        return;
      }}

      let html = '<div class="members-grid">';
      members.forEach((name, idx) => {{
        html += `
          <div class="member-item">
            <span class="member-num">#${{idx + 1}}</span>
            <span class="member-name" title="${{escapeHtml(name)}}">${{escapeHtml(name)}}</span>
          </div>
        `;
      }});
      html += '</div>';
      container.innerHTML = html;
    }};

    let currentPeriod = {_to_js(default_period)};

    const updateDashboard = (periodKey) => {{
      currentPeriod = periodKey;
      const data = periodsData[periodKey] || periodsData['all'] || {{}};

      // Chips
      const periodDesc = isMs ? (data.period_desc_ms || data.label_ms) : (data.period_desc_en || data.label_en);
      document.getElementById('chipPeriod').textContent = t.period_prefix + (periodDesc || periodKey);
      document.getElementById('chipApproved').textContent = t.approved_prefix + (data.approved ?? 0);
      document.getElementById('chipApplications').textContent = t.applications_prefix + (data.total_applications ?? 0);
      document.getElementById('chipPending').textContent = t.pending_prefix + (data.pending ?? 0);
      document.getElementById('chipRejected').textContent = t.rejected_prefix + (data.rejected ?? 0);

      // Course Chart
      const cDist = data.course_distribution || [];
      const cLabels = cDist.map(i => i.label);
      const cValues = cDist.map(i => i.pct);
      if (cLabels.length > 0) {{
        courseChart.data.labels = cLabels;
        courseChart.data.datasets[0].data = cValues;
        courseChart.data.datasets[0].backgroundColor = cLabels.map((_, i) => CHART_THEME.palette[i % CHART_THEME.palette.length]);
        courseChart.options.plugins.centerText.text = cLabels.length;
      }} else {{
        courseChart.data.labels = [t.no_data];
        courseChart.data.datasets[0].data = [100];
        courseChart.data.datasets[0].backgroundColor = ['#22314f'];
        courseChart.options.plugins.centerText.text = 0;
      }}
      courseChart.update();

      // Birth Chart
      const bDist = data.birth_year_distribution || [];
      const bLabels = bDist.map(i => i.label);
      const bValues = bDist.map(i => i.pct);
      if (bLabels.length > 0) {{
        birthChart.data.labels = bLabels;
        birthChart.data.datasets[0].data = bValues;
        birthChart.data.datasets[0].backgroundColor = bLabels.map((_, i) => CHART_THEME.palette[i % CHART_THEME.palette.length]);
        birthChart.options.plugins.centerText.text = bLabels.length;
      }} else {{
        birthChart.data.labels = [t.no_data];
        birthChart.data.datasets[0].data = [100];
        birthChart.data.datasets[0].backgroundColor = ['#22314f'];
        birthChart.options.plugins.centerText.text = 0;
      }}
      birthChart.update();

      // Members List
      document.getElementById('memberSearch').value = '';
      renderMembersList(data.members || []);
    }};

    // Event listener for dropdown selection
    document.getElementById('periodSelect').addEventListener('change', (e) => {{
      updateDashboard(e.target.value);
    }});

    // Event listener for real-time member search
    document.getElementById('memberSearch').addEventListener('input', (e) => {{
      const query = e.target.value.toLowerCase().trim();
      const allMembers = (periodsData[currentPeriod] || {{}}).members || [];
      const filtered = query ? allMembers.filter(n => n.toLowerCase().includes(query)) : allMembers;
      renderMembersList(filtered, query);
    }});

    // Initial render
    updateDashboard(currentPeriod);
  </script>
</body>
</html>"""
