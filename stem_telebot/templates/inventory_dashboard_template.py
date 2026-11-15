"""Read-only inventory dashboard HTML template."""

import html


def _esc(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def _item_state(qty, min_qty):
    if qty <= 0:
        return "out", "OUT"
    if min_qty > 0 and qty <= min_qty:
        return "low", "LOW"
    return "ok", "OK"


def render_inventory_dashboard(
    *,
    favicon_tag: str,
    logo_src: str,
    generated_at: str,
    total_items: int,
    total_units: int,
    low_stock_count: int,
    items: list[dict],
    log_entries: list[dict],
) -> str:
    rows = []
    for item in items:
        qty = int(item.get("qty", 0))
        min_qty = int(item.get("min_qty", 0))
        state, badge = _item_state(qty, min_qty)
        rows.append(
            f'<tr class="{state}">'
            f'<td class="mono">{_esc(item.get("id"))}</td>'
            f'<td>{_esc(item.get("name"))}</td>'
            f'<td>{_esc(item.get("category"))}</td>'
            f'<td class="num"><b>{qty}</b> <span class="muted">{_esc(item.get("unit"))}</span></td>'
            f'<td>{_esc(item.get("location"))}</td>'
            f'<td class="num">{min_qty}</td>'
            f'<td><span class="badge {state}">{badge}</span></td>'
            f'<td class="muted">{_esc(item.get("updated_at"))}</td>'
            "</tr>"
        )
    if not rows:
        rows.append('<tr><td colspan="8" class="empty">No inventory items yet.</td></tr>')

    log_rows = []
    for entry in log_entries:
        delta = int(entry.get("delta", 0))
        delta_cls = "in" if delta >= 0 else "out"
        delta_text = f"+{delta}" if delta > 0 else str(delta)
        log_rows.append(
            "<tr>"
            f'<td class="muted">{_esc(entry.get("timestamp"))}</td>'
            f'<td class="mono">{_esc(entry.get("item_id"))}</td>'
            f'<td>{_esc(entry.get("item"))}</td>'
            f'<td class="num delta {delta_cls}">{delta_text}</td>'
            f'<td class="num">{_esc(entry.get("balance"))}</td>'
            f'<td>{_esc(entry.get("reason"))}</td>'
            f'<td class="muted">{_esc(entry.get("by"))}</td>'
            "</tr>"
        )
    if not log_rows:
        log_rows.append('<tr><td colspan="7" class="empty">No movements recorded yet.</td></tr>')

    logo_tag = (
        f'<img class="logo" src="{logo_src}" alt="STEM logo" />' if logo_src else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>STEM Inventory</title>
  {favicon_tag}
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
      --ok: #34d399;
      --low: #fbbf24;
      --out: #f87171;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      padding: 24px 16px 56px;
      color: var(--text);
      font-family: "Inter", "Segoe UI", Arial, sans-serif;
      background: var(--bg);
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      background:
        radial-gradient(ellipse 700px 500px at 15% 0%, rgba(33, 62, 128, 0.30), transparent),
        radial-gradient(ellipse 600px 400px at 90% 100%, rgba(204, 145, 43, 0.15), transparent);
      pointer-events: none;
    }}
    .wrap {{ position: relative; width: min(1120px, 100%); margin: 0 auto; }}
    header {{ display: flex; align-items: center; gap: 14px; margin-bottom: 22px; }}
    .logo {{ width: 46px; height: 46px; border-radius: 12px; object-fit: contain; background: #0b1428; }}
    h1 {{ font-size: 22px; margin: 0; letter-spacing: 0.2px; }}
    .sub {{ color: var(--muted); font-size: 13px; margin-top: 3px; }}
    .cards {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 22px; }}
    .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 14px 16px; }}
    .card .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.6px; }}
    .card .value {{ font-size: 26px; font-weight: 800; margin-top: 4px; }}
    .card.low .value {{ color: var(--low); }}
    section {{ background: var(--panel); border: 1px solid var(--line); border-radius: 16px; padding: 6px 0 0; margin-bottom: 20px; overflow: hidden; }}
    h2 {{ font-size: 15px; margin: 14px 18px 10px; color: #cbd5e1; }}
    .scroll {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; white-space: nowrap; }}
    th {{ text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--muted); padding: 10px 12px; border-bottom: 1px solid var(--line); }}
    td {{ padding: 10px 12px; border-bottom: 1px solid rgba(34, 49, 79, 0.55); }}
    tr:last-child td {{ border-bottom: none; }}
    tr.low td {{ background: rgba(251, 191, 36, 0.06); }}
    tr.out td {{ background: rgba(248, 113, 113, 0.08); }}
    .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .mono {{ font-family: "SFMono-Regular", Consolas, monospace; font-size: 12px; color: #cbd5e1; }}
    .muted {{ color: var(--muted); }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 10px; font-weight: 700; letter-spacing: 0.5px; }}
    .badge.ok {{ color: var(--ok); background: rgba(52, 211, 153, 0.14); }}
    .badge.low {{ color: var(--low); background: rgba(251, 191, 36, 0.16); }}
    .badge.out {{ color: var(--out); background: rgba(248, 113, 113, 0.16); }}
    .delta.in {{ color: var(--ok); }}
    .delta.out {{ color: var(--out); }}
    .empty {{ text-align: center; color: var(--muted); padding: 26px 12px; }}
    footer {{ text-align: center; color: var(--muted); font-size: 12px; margin-top: 8px; }}
    @media (max-width: 560px) {{
      .cards {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 19px; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      {logo_tag}
      <div>
        <h1>STEM Inventory</h1>
        <div class="sub">Operations &amp; logistics stock levels</div>
      </div>
    </header>

    <div class="cards">
      <div class="card">
        <div class="label">Items</div>
        <div class="value">{total_items}</div>
      </div>
      <div class="card">
        <div class="label">Total Units</div>
        <div class="value">{total_units}</div>
      </div>
      <div class="card low">
        <div class="label">Low / Out of Stock</div>
        <div class="value">{low_stock_count}</div>
      </div>
    </div>

    <section>
      <h2>Current Stock</h2>
      <div class="scroll">
        <table>
          <thead>
            <tr>
              <th>ID</th><th>Name</th><th>Category</th><th class="num">Qty</th>
              <th>Location</th><th class="num">Min</th><th>Status</th><th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {"".join(rows)}
          </tbody>
        </table>
      </div>
    </section>

    <section>
      <h2>Recent Movements</h2>
      <div class="scroll">
        <table>
          <thead>
            <tr>
              <th>Time</th><th>ID</th><th>Item</th><th class="num">Change</th>
              <th class="num">Balance</th><th>Reason</th><th>By</th>
            </tr>
          </thead>
          <tbody>
            {"".join(log_rows)}
          </tbody>
        </table>
      </div>
    </section>

    <footer>Generated {_esc(generated_at)} · read-only view</footer>
  </div>
</body>
</html>
"""
