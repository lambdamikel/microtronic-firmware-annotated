#!/usr/bin/env python3
"""Render the annotated Microtronic firmware ROM to a single, self-contained HTML page.

Reads the canonical disassembly plus the annotation TSVs and emits ../index.html:
a browsable, colour-coded, cross-linked view of all 64 pages, with a page/routine
sidebar, live search, an "annotated only" filter, and light/dark themes.

Self-contained (inline CSS/JS, no external requests) so it works offline and on
GitHub Pages. Run from the repo root:  python3 dev-support/build_html.py
"""
import html
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "rom", "microtronic-firmware-disassembled.txt")
ANN = os.path.join(ROOT, "annotated", "annotations.tsv")
BAN = os.path.join(ROOT, "annotated", "banners.tsv")
OUT = os.path.join(ROOT, "index.html")

RIGHT_RE = re.compile(
    r"\s*([0-9a-f]{2}):([0-9a-f]{2})\s+\([0-9a-f]{2}:[0-9a-f]{2}\)\s+([0-9a-f]{2})\s+-\s*(.*)"
)
REF_RE = re.compile(r"\b([0-3][0-9a-f]):([0-3][0-9a-f])\b")

# mnemonic -> token class (drives colour)
FLOW = {"BR", "CALL", "RETN", "LDP", "TPC"}
IO = {"SETR", "RSTR", "TDO", "TKA", "KNEZ"}
TEST = {"MNEA", "MNEZ", "YNEA", "YNEC", "ALEM", "ALEC", "TBIT", "TBIT1",
        "CPAIZ", "SAMAN", "IMAC", "DMAN"}


def load_tsv(path):
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#") or "\t" not in line:
                continue
            k, v = line.split("\t", 1)
            out[k.strip()] = v.strip()
    return out


def mn_class(mnem, hexb):
    if mnem == "MNEA" and hexb == "00":
        return "pad"
    if mnem in FLOW:
        return "flow"
    if mnem in IO:
        return "io"
    if mnem in TEST:
        return "test"
    return "mn"


def linkify(escaped):
    return REF_RE.sub(
        lambda m: f'<a class="xref" href="#L{m.group(1)}{m.group(2)}">{m.group(1)}:{m.group(2)}</a>',
        escaped,
    )


def esc(s):
    return html.escape(s, quote=True)


def main():
    comments = load_tsv(ANN)
    banners = load_tsv(BAN)

    pages = []          # list of (page, [rows])
    cur = None
    n_ann = n_total = 0
    with open(SRC, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if line.startswith("# Page"):
                page = line.split()[2]
                cur = (page, [])
                pages.append(cur)
                continue
            if "#" not in line:
                continue
            left, _, right = line.partition("#")
            if not left.strip():
                continue
            m = RIGHT_RE.match(right)
            if not m:
                continue
            pg, off, hexb, _src_c = m.groups()
            parts = left.split()
            mnem = parts[0]
            operand = parts[1] if len(parts) > 1 else ""
            addr = pg + off
            comment = comments.get(f"{pg}:{off}", "")
            banner = banners.get(f"{pg}:{off}", "")
            n_total += 1
            if comment:
                n_ann += 1
            cur[1].append((addr, pg, off, mnem, operand, hexb, comment, banner))

    coverage = f"{n_ann}/{n_total}"
    pct = (100.0 * n_ann / n_total) if n_total else 0

    # ---- build the nav (chapters -> pages, + named routines from banners) ----
    nav = []
    for chap in range(4):
        nav.append(f'<div class="navchap">Chapter {chap}</div>')
        nav.append('<div class="navpages">')
        for p in range(16):
            page = f"{chap*16+p:02x}"
            nav.append(f'<a href="#P{page}" class="navpg">{page}</a>')
        nav.append("</div>")
    nav_html = "\n".join(nav)

    routines = []
    for page, rows in pages:
        for (addr, pg, off, *_rest, banner) in rows:
            if banner:
                label = re.split(r"[.(]", banner.replace("\\n", " "))[0].strip()
                if len(label) > 46:
                    label = label[:44] + "…"
                routines.append(
                    f'<a href="#L{addr}" class="navrt"><span class="navaddr">{pg}:{off}</span>{esc(label)}</a>'
                )
    routines_html = "\n".join(routines)

    # ---- build the listing ----
    body = []
    for page, rows in pages:
        chap, pp = int(page, 16) // 16, int(page, 16) % 16
        body.append(
            f'<section class="page"><h2 id="P{page}">Page {page}'
            f'<span class="cp">chapter {chap} · page {pp:x}</span></h2>'
        )
        for (addr, pg, off, mnem, operand, hexb, comment, banner) in rows:
            if banner:
                for seg in banner.split("\\n"):
                    body.append(f'<div class="banner">{linkify(esc(seg))}</div>')
            cls = mn_class(mnem, hexb)
            data_ann = "1" if comment else "0"
            search = esc(f"{pg}:{off} {mnem} {operand} {comment}".lower())
            cm = f'<span class="cm">{linkify(esc(comment))}</span>' if comment else ""
            op = f'<span class="op">{esc(operand)}</span>' if operand else ""
            body.append(
                f'<div class="row" id="L{addr}" data-a="{data_ann}" data-s="{search}">'
                f'<a class="addr" href="#L{addr}">{pg}:{off}</a>'
                f'<span class="hex">{hexb}</span>'
                f'<span class="{cls}">{esc(mnem)}</span>{op}{cm}</div>'
            )
        body.append("</section>")
    body_html = "\n".join(body)

    page_html = TEMPLATE.format(
        nav=nav_html, routines=routines_html, body=body_html,
        coverage=coverage, pct=f"{pct:.1f}",
    )
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(page_html)
    print(f"wrote {OUT}  ({len(page_html)//1024} KB, {n_total} instructions, {coverage} annotated)")


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Busch Microtronic 2090 &mdash; Annotated Firmware ROM</title>
<style>
:root {{
  --bg:#f7f7f8; --panel:#ffffff; --line:#e6e6ea; --fg:#1b1d22; --dim:#8a8f98;
  --addr:#8a8f98; --hex:#b7bcc4; --flow:#c0392b; --io:#1f8a54; --test:#b26a00;
  --op:#2563eb; --cm:#5a6472; --xref:#2563eb; --accent:#6d3fd4; --bannerbg:#efeafc;
}}
:root[data-theme="dark"], @media (prefers-color-scheme: dark) {{}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg:#0d1117; --panel:#0f141b; --line:#20262e; --fg:#c9d1d9; --dim:#7d8590;
    --addr:#6e7681; --hex:#4b535d; --flow:#ff7b72; --io:#7ee787; --test:#e3b341;
    --op:#79c0ff; --cm:#8b949e; --xref:#79c0ff; --accent:#bd93f9; --bannerbg:#161b26;
  }}
}}
:root[data-theme="light"] {{
  --bg:#f7f7f8; --panel:#ffffff; --line:#e6e6ea; --fg:#1b1d22; --dim:#8a8f98;
  --addr:#8a8f98; --hex:#b7bcc4; --flow:#c0392b; --io:#1f8a54; --test:#b26a00;
  --op:#2563eb; --cm:#5a6472; --xref:#2563eb; --accent:#6d3fd4; --bannerbg:#efeafc;
}}
:root[data-theme="dark"] {{
  --bg:#0d1117; --panel:#0f141b; --line:#20262e; --fg:#c9d1d9; --dim:#7d8590;
  --addr:#6e7681; --hex:#4b535d; --flow:#ff7b72; --io:#7ee787; --test:#e3b341;
  --op:#79c0ff; --cm:#8b949e; --xref:#79c0ff; --accent:#bd93f9; --bannerbg:#161b26;
}}
* {{ box-sizing:border-box; }}
html {{ scroll-behavior:smooth; }}
body {{ margin:0; background:var(--bg); color:var(--fg);
  font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
code, .mono {{ font-family:"SFMono-Regular",ui-monospace,Menlo,Consolas,monospace; }}
a {{ color:var(--xref); text-decoration:none; }}
a:hover {{ text-decoration:underline; }}
header {{ padding:22px 26px 16px; border-bottom:1px solid var(--line);
  background:var(--panel); position:sticky; top:0; z-index:10; }}
header h1 {{ margin:0 0 4px; font-size:19px; }}
header h1 .sub {{ color:var(--dim); font-weight:400; }}
.meta {{ color:var(--dim); font-size:12.5px; margin:2px 0 12px; }}
.meta a {{ color:var(--accent); }}
.controls {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; }}
.controls input[type=search] {{ flex:1; min-width:180px; padding:7px 10px;
  border:1px solid var(--line); border-radius:7px; background:var(--bg); color:var(--fg); font-size:13px; }}
.btn {{ padding:7px 11px; border:1px solid var(--line); border-radius:7px;
  background:var(--bg); color:var(--fg); cursor:pointer; font-size:12.5px; }}
.btn.on {{ background:var(--accent); color:#fff; border-color:var(--accent); }}
.legend {{ display:flex; gap:14px; flex-wrap:wrap; font-size:11.5px; color:var(--dim); margin-top:10px; }}
.legend span b {{ font-weight:600; }}
.wrap {{ display:grid; grid-template-columns:230px 1fr; align-items:start; }}
nav {{ position:sticky; top:0; align-self:start; max-height:100vh; overflow:auto;
  border-right:1px solid var(--line); padding:14px 10px 40px; background:var(--panel); }}
.navchap {{ font-size:11px; text-transform:uppercase; letter-spacing:.06em;
  color:var(--dim); margin:14px 6px 6px; }}
.navpages {{ display:grid; grid-template-columns:repeat(8,1fr); gap:3px; margin-bottom:4px; }}
.navpg {{ text-align:center; padding:3px 0; border-radius:5px; font:12px ui-monospace,monospace;
  color:var(--fg); }}
.navpg:hover {{ background:var(--bannerbg); text-decoration:none; }}
.navsec {{ font-size:11px; text-transform:uppercase; letter-spacing:.06em;
  color:var(--dim); margin:18px 6px 6px; }}
.navrt {{ display:block; padding:4px 6px; border-radius:5px; color:var(--fg);
  font-size:12px; line-height:1.35; }}
.navrt:hover {{ background:var(--bannerbg); text-decoration:none; }}
.navaddr {{ font:11px ui-monospace,monospace; color:var(--accent); margin-right:6px; }}
main {{ padding:8px 20px 120px; min-width:0; }}
.page {{ margin-top:26px; }}
.page h2 {{ font:600 15px ui-monospace,monospace; margin:0 0 6px; padding-bottom:5px;
  border-bottom:1px solid var(--line); }}
.page h2 .cp {{ color:var(--dim); font-weight:400; font-size:12px; margin-left:10px; }}
.banner {{ background:var(--bannerbg); border-left:3px solid var(--accent);
  padding:7px 12px; margin:12px 0 5px; border-radius:0 6px 6px 0; font-size:12.5px; color:var(--fg); }}
.row {{ display:grid; grid-template-columns:52px 26px 62px minmax(24px,auto) 1fr;
  gap:8px; padding:1px 6px; border-radius:4px; align-items:baseline; }}
.row:hover {{ background:var(--bannerbg); }}
.row:target {{ background:var(--bannerbg); box-shadow:inset 3px 0 0 var(--accent); }}
.addr {{ font:12px ui-monospace,monospace; color:var(--addr); }}
.hex {{ font:12px ui-monospace,monospace; color:var(--hex); text-align:right; }}
.mn,.flow,.io,.test,.pad,.op {{ font:12.5px ui-monospace,monospace; }}
.mn {{ color:var(--fg); }} .flow {{ color:var(--flow); }} .io {{ color:var(--io); }}
.test {{ color:var(--test); }} .pad {{ color:var(--hex); }}
.op {{ color:var(--op); }}
.cm {{ color:var(--cm); font-style:italic; grid-column:5; }}
.cm .xref {{ color:var(--xref); font-style:normal; }}
.hide {{ display:none !important; }}
body.annonly .row[data-a="0"] {{ display:none; }}
footer {{ color:var(--dim); font-size:12px; text-align:center; padding:30px 20px 60px; }}
@media (max-width:760px) {{
  .wrap {{ grid-template-columns:1fr; }}
  nav {{ position:static; max-height:none; border-right:none; border-bottom:1px solid var(--line); }}
  .navpages {{ grid-template-columns:repeat(16,1fr); }}
  .row {{ grid-template-columns:48px 24px 56px minmax(20px,auto) 1fr; }}
}}
</style>
</head>
<body>
<header>
  <h1>Busch Microtronic 2090 <span class="sub">&mdash; Annotated Firmware ROM</span></h1>
  <div class="meta">
    The 1981 TMS1600 operating-system ROM, disassembled and annotated &nbsp;&middot;&nbsp;
    <b>{coverage}</b> instructions annotated ({pct}%) &nbsp;&middot;&nbsp;
    <a href="https://github.com/lambdamikel/microtronic-firmware-annotated">repo</a> &middot;
    <a href="https://github.com/lambdamikel/microtronic-firmware-annotated/blob/master/docs/02-how-the-microtronic-works.md">how it works</a> &middot;
    <a href="https://github.com/lambdamikel/microtronic-firmware-annotated/blob/master/docs/04-discoveries.md">discoveries</a>
  </div>
  <div class="controls">
    <input id="q" type="search" placeholder="Search mnemonics, addresses, annotations&hellip;" autocomplete="off">
    <button id="annBtn" class="btn">Annotated only</button>
    <button id="themeBtn" class="btn">Theme</button>
  </div>
  <div class="legend">
    <span><b style="color:var(--flow)">flow</b> branch/call/paging</span>
    <span><b style="color:var(--io)">io</b> R/O/K lines</span>
    <span><b style="color:var(--test)">test</b> sets status</span>
    <span><b style="color:var(--op)">operand</b></span>
    <span><b style="color:var(--cm)">annotation</b> (click <b style="color:var(--xref)">nn:nn</b> refs to jump)</span>
  </div>
</header>
<div class="wrap">
  <nav>
    {nav}
    <div class="navsec">Routines</div>
    {routines}
  </nav>
  <main>
    {body}
    <footer>
      Firmware &copy; 1981 Busch GmbH, published by permission &mdash; for reference only.<br>
      Annotations CC&nbsp;BY&nbsp;4.0. Reverse engineered by Claude Opus 4.8, directed by Michael&nbsp;A.&nbsp;Wessel.
    </footer>
  </main>
</div>
<script>
(function() {{
  var q = document.getElementById('q'), rows = document.querySelectorAll('.row');
  q.addEventListener('input', function() {{
    var t = q.value.trim().toLowerCase();
    rows.forEach(function(r) {{
      r.classList.toggle('hide', t && r.dataset.s.indexOf(t) === -1);
    }});
  }});
  var ann = document.getElementById('annBtn');
  ann.addEventListener('click', function() {{
    document.body.classList.toggle('annonly');
    ann.classList.toggle('on');
  }});
  var tb = document.getElementById('themeBtn');
  tb.addEventListener('click', function() {{
    var cur = document.documentElement.getAttribute('data-theme');
    var mq = window.matchMedia('(prefers-color-scheme: dark)').matches;
    var next = (cur ? cur === 'dark' : mq) ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    try {{ localStorage.setItem('mt-theme', next); }} catch(e) {{}}
  }});
  try {{ var s = localStorage.getItem('mt-theme'); if (s) document.documentElement.setAttribute('data-theme', s); }} catch(e) {{}}
}})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
