"""
Membership profile HTML template.
"""


def render_membership_card(
    *,
    membership_id: str,
    name: str,
    matric: str,
    program: str,
    register_date: str,
    expired_date: str,
    badge_class: str,
    badge_text: str,
    logo_src: str,
    favicon_tag: str,
) -> str:
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>STEM Membership Card</title>
  {favicon_tag}
  <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">
  <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>
  <link href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&family=Space+Grotesk:wght@500;600;700&display=swap\" rel=\"stylesheet\">
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{
      min-height:100vh;
      font-family:'Inter',system-ui,sans-serif;
      background:#050a18;
      color:#f1f5f9;
      display:flex;align-items:center;justify-content:center;
      padding:24px 16px;
      overflow-x:hidden;
    }}
    body::before{{
      content:'';position:fixed;inset:0;
      background:
        radial-gradient(ellipse 700px 500px at 20% 10%,rgba(33,62,128,0.25),transparent),
        radial-gradient(ellipse 600px 400px at 80% 90%,rgba(204,145,43,0.15),transparent);
      pointer-events:none;z-index:0;
    }}

    .scene{{position:relative;z-index:1;width:100%;max-width:480px}}

    .card{{
      position:relative;
      border-radius:20px;
      overflow:hidden;
      background:linear-gradient(145deg,#0f1b38 0%,#142042 40%,#17244a 100%);
      border:1px solid rgba(148,163,184,0.12);
      box-shadow:
        0 2px 4px rgba(0,0,0,0.3),
        0 12px 40px rgba(0,0,0,0.5),
        inset 0 1px 0 rgba(255,255,255,0.04);
      aspect-ratio:auto;
    }}

    .card::before{{
      content:'';position:absolute;inset:0;
      background-image:
        linear-gradient(rgba(255,255,255,0.02) 1px,transparent 1px),
        linear-gradient(90deg,rgba(255,255,255,0.02) 1px,transparent 1px);
      background-size:32px 32px;
      mask-image:linear-gradient(180deg,rgba(0,0,0,0.4),transparent 70%);
      pointer-events:none;z-index:1;
    }}

    .card::after{{
      content:'';position:absolute;inset:0;z-index:5;pointer-events:none;
      background:linear-gradient(
        105deg,
        transparent 38%,
        rgba(255,255,255,0.06) 42%,
        rgba(255,255,255,0.10) 50%,
        rgba(255,255,255,0.06) 58%,
        transparent 62%
      );
      background-size:250% 100%;
      animation:shimmer 9s ease-in-out infinite;
    }}
    @keyframes shimmer{{
      0%{{background-position:200% 0}}
      100%{{background-position:-200% 0}}
    }}

    .card-inner{{position:relative;z-index:2;padding:24px 22px 20px}}

    .top-bar{{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}}
    .brand{{display:flex;align-items:center;gap:10px}}
    .logo{{
      width:36px;height:36px;border-radius:8px;object-fit:cover;
      border:1px solid rgba(255,255,255,0.12);
      background:rgba(255,255,255,0.06);
    }}
    .org{{
      font-family:'Space Grotesk','Inter',sans-serif;
      font-size:13px;font-weight:700;letter-spacing:0.06em;
      color:rgba(226,232,240,0.85);text-transform:uppercase;
    }}
    .badge{{
      font-family:'Space Grotesk',sans-serif;
      font-size:11px;font-weight:700;letter-spacing:0.06em;
      padding:5px 12px;border-radius:999px;
      text-transform:uppercase;
      backdrop-filter:blur(8px);
    }}
    .badge.verified{{
      background:rgba(34,197,94,0.14);
      border:1px solid rgba(34,197,94,0.4);
      color:#86efac;
      box-shadow:0 0 12px rgba(34,197,94,0.15);
    }}
    .badge.pending{{
      background:rgba(250,204,21,0.14);
      border:1px solid rgba(250,204,21,0.4);
      color:#fde68a;
    }}
    .badge.expired{{
      background:rgba(239,68,68,0.14);
      border:1px solid rgba(239,68,68,0.4);
      color:#fca5a5;
    }}

    .mid-section{{margin-bottom:14px}}
    .mid-label{{
      font-size:9px;font-weight:600;letter-spacing:0.14em;
      text-transform:uppercase;color:rgba(148,163,184,0.6);
      margin-bottom:6px;
    }}
    .mid-value{{
      font-family:'JetBrains Mono',monospace;
      font-size:clamp(18px,4.5vw,24px);font-weight:700;
      letter-spacing:0.08em;color:#f8fafc;
      word-break:break-all;
    }}

    .name-row{{
      display:flex;align-items:flex-end;justify-content:space-between;
      gap:12px;margin-bottom:16px;flex-wrap:wrap;
    }}
    .name-block .lbl{{
      font-size:9px;font-weight:600;letter-spacing:0.12em;
      text-transform:uppercase;color:rgba(148,163,184,0.5);
      margin-bottom:3px;
    }}
    .name-block .val{{
      font-family:'Space Grotesk',sans-serif;
      font-size:15px;font-weight:600;color:#e2e8f0;
      text-transform:uppercase;letter-spacing:0.03em;
    }}

    .details{{
      display:grid;grid-template-columns:1fr 1fr;gap:0;
      border-top:1px solid rgba(148,163,184,0.08);
      padding-top:14px;
    }}
    .det{{padding:6px 0}}
    .det .lbl{{
      font-size:9px;font-weight:600;letter-spacing:0.1em;
      text-transform:uppercase;color:rgba(148,163,184,0.45);
      margin-bottom:2px;
    }}
    .det .val{{
      font-family:'JetBrains Mono',monospace;
      font-size:12px;font-weight:500;color:rgba(226,232,240,0.8);
      letter-spacing:0.02em;
    }}
    .det .val.text{{
      font-family:'Space Grotesk',sans-serif;
      letter-spacing:0.01em;
    }}

    .copy-btn{{
      position:absolute;top:14px;right:14px;z-index:6;
      width:34px;height:34px;border-radius:10px;
      border:1px solid rgba(148,163,184,0.15);
      background:rgba(15,23,42,0.6);
      backdrop-filter:blur(10px);
      color:rgba(226,232,240,0.5);
      cursor:pointer;display:grid;place-items:center;
      transition:all 0.2s ease;
      opacity:0;
    }}
    .card:hover .copy-btn,.card:focus-within .copy-btn{{opacity:1}}
    .copy-btn:hover{{
      background:rgba(51,65,85,0.7);
      color:#e2e8f0;
      border-color:rgba(148,163,184,0.3);
    }}
    .copy-btn svg{{width:15px;height:15px}}

    .card-footer{{
      display:flex;align-items:center;justify-content:space-between;
      padding:12px 22px;
      background:rgba(0,0,0,0.2);
      border-top:1px solid rgba(148,163,184,0.06);
    }}
    .footer-label{{
      font-size:10px;color:rgba(148,163,184,0.4);
      font-weight:500;letter-spacing:0.02em;
    }}
    .footer-dots{{display:flex;gap:3px;}}
    .footer-dots span{{
      width:4px;height:4px;border-radius:50%;
      background:rgba(148,163,184,0.2);
    }}
    .footer-dots span:first-child{{background:rgba(204,145,43,0.5)}}
    .footer-dots span:nth-child(2){{background:rgba(33,62,128,0.5)}}

    .mobile-copy{{
      display:none;
      margin-top:14px;
      width:100%;
      padding:12px;border-radius:14px;
      border:1px solid rgba(148,163,184,0.1);
      background:rgba(15,23,42,0.5);
      backdrop-filter:blur(10px);
      color:rgba(226,232,240,0.7);
      font-family:'Space Grotesk',sans-serif;
      font-size:13px;font-weight:600;
      cursor:pointer;transition:all 0.2s;
      text-align:center;
    }}
    .mobile-copy:hover{{
      background:rgba(51,65,85,0.5);
      color:#e2e8f0;
    }}

    .toast{{
      position:fixed;bottom:20px;left:50%;transform:translateX(-50%) translateY(8px);
      background:rgba(15,23,42,0.92);
      border:1px solid rgba(148,163,184,0.2);
      backdrop-filter:blur(12px);
      color:#e2e8f0;border-radius:12px;
      padding:10px 18px;font-size:13px;font-weight:600;
      opacity:0;transition:all 0.25s ease;
      z-index:100;pointer-events:none;
      font-family:'Space Grotesk',sans-serif;
    }}
    .toast.show{{opacity:1;transform:translateX(-50%) translateY(0)}}

    @media(max-width:520px){{
      .card-inner{{padding:20px 18px 16px}}
      .card-footer{{padding:10px 18px}}
      .copy-btn{{opacity:1;top:auto;bottom:58px;right:18px;
        width:30px;height:30px;border-radius:8px}}
      .mobile-copy{{display:block}}
      .name-row{{flex-direction:column;align-items:flex-start;gap:8px}}
    }}
  </style>
</head>
<body>
  <div class=\"scene\">
    <div class=\"card\" id=\"memberCard\">
      <button class=\"copy-btn\" id=\"copyBtn\" type=\"button\" title=\"Copy Membership ID\">
        <svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\">
          <rect x=\"9\" y=\"9\" width=\"13\" height=\"13\" rx=\"2\"/>
          <path d=\"M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1\"/>
        </svg>
      </button>
      <div class=\"card-inner\">

        <div class=\"top-bar\">
          <div class=\"brand\">
            <img class=\"logo\" src=\"{logo_src}\" alt=\"STEM\" />
            <span class=\"org\">Membership STEM</span>
          </div>
          <div class=\"badge {badge_class}\">{badge_text}</div>
        </div>

        <div class=\"mid-section\">
          <div class=\"mid-label\">Membership ID</div>
          <div class=\"mid-value\">{membership_id}</div>
        </div>

        <div class=\"name-row\">
          <div class=\"name-block\">
            <div class=\"lbl\">Card Holder</div>
            <div class=\"val\">{name}</div>
          </div>
          <div class=\"name-block\">
            <div class=\"lbl\">Matric</div>
            <div class=\"val\">{matric}</div>
          </div>
        </div>

        <div class=\"details\">
          <div class=\"det\">
            <div class=\"lbl\">Program</div>
            <div class=\"val text\">{program}</div>
          </div>
          <div class=\"det\">
            <div class=\"lbl\">Status</div>
            <div class=\"val text\">{badge_text}</div>
          </div>
          <div class=\"det\">
            <div class=\"lbl\">Valid From</div>
            <div class=\"val\">{register_date}</div>
          </div>
          <div class=\"det\">
            <div class=\"lbl\">Valid Thru</div>
            <div class=\"val\">{expired_date}</div>
          </div>
        </div>
      </div>

      <div class=\"card-footer\">
        <span class=\"footer-label\">STEM USAS &bull; Digital Member Card</span>
        <div class=\"footer-dots\"><span></span><span></span><span></span></div>
      </div>
    </div>

    <button class=\"mobile-copy\" id=\"mobileCopyBtn\" type=\"button\">Copy Membership ID</button>
  </div>

  <div class=\"toast\" id=\"toast\">Copied!</div>

  <script>
    const mid = {membership_id!r};
    const show = (t) => {{
      const el = document.getElementById('toast');
      el.textContent = t;
      el.classList.add('show');
      setTimeout(() => el.classList.remove('show'), 1500);
    }};
    const copy = async () => {{
      try {{ await navigator.clipboard.writeText(mid); show('Membership ID copied'); }}
      catch {{ show('Copy failed'); }}
    }};
    document.getElementById('copyBtn').addEventListener('click', copy);
    document.getElementById('mobileCopyBtn').addEventListener('click', copy);
  </script>
</body>
</html>"""
