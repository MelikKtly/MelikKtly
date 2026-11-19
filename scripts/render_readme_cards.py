#!/usr/bin/env python3
"""
Renders the animated SVG cards for the GitHub profile README.

  python scripts/render_readme_cards.py            # fetch fresh data + render
  OFFLINE=1 python scripts/render_readme_cards.py  # use cached data only
  STATIC=1  python scripts/render_readme_cards.py  # no animation, final frame

Everything visual lives inside SVGs shown through <img>, so only inline <style>
(CSS keyframes) and embedded base64 fonts / images are used. No JavaScript.
"""
import base64, datetime as dt, html, io, json, os, re, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARDS, DATA, FONTS, ASSETS = ROOT / "cards", ROOT / "data", ROOT / "fonts", ROOT / "assets"

# ───────────────────────── edit me ─────────────────────────
USER = "MelikKtly"
FIRST, LAST = "Melik Kutlay", "Atilla"
EYEBROW = "MERHABA, BEN"
BIO = [
    "Software developer & student at Süleyman Demirel University.",
    "Java · Python · TypeScript — full-stack apps and AI projects.",
]
LOCATION = "Türkiye"
PORTRAIT = "ascii"  # "ascii" uses assets/portrait.txt, "photo" embeds the picture itself
LINKEDIN = "https://www.linkedin.com/in/melik-kutlay-atilla"
FEATURED = [  # name, fallback description, fallback language
    ("CoreSport", "AI-powered athlete development platform.", "TypeScript"),
    ("MPF3", "My fitness tracker website.", "JavaScript"),
    ("Smart-Email-Writer-Assistant", "An AI project designed to assist with writing emails.", "Java"),
    ("KurumsalAIAsistan", "Corporate AI assistant.", "Python"),
]
STACK = ["Java", "Python", "TypeScript", "JavaScript", "Node.js", "Express.js", "Next.js",
         "Spring", "MySQL", "MongoDB", "NumPy", "Pandas", "JWT"]
# ───────────────────────────────────────────────────────────

PAPER, INK, MUTED, LINE, DEEP = "#131316", "#ECE9E2", "#8A8882", "#2B2B31", "#0A0A0C"
BLUE, RED, YELLOW = "#4A72FF", "#E5484D", "#F2B11C"
TILE_BLUE, TILE_RED, TILE_YELLOW = "#1F3FC4", "#A8282E", "#C98A00"
BAR, CHIP = "#4A4A53", "#1C1C21"
GRAPH = ["#1F1F25", "#1C2C66", "#2743A8", "#3B63EB", "#86A2FF"]
LANG = {"TypeScript": "#3178C6", "JavaScript": "#E9C600", "Java": "#B07219", "Python": "#3572A5",
        "MATLAB": "#E16737", "HTML": "#E34C26", "CSS": "#663399", "Jupyter Notebook": "#DA5B0B"}
STATIC = os.environ.get("STATIC") == "1"
OFFLINE = os.environ.get("OFFLINE") == "1"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

# ───────────────────────── fonts ─────────────────────────
FACES = [("Instrument Serif", "normal", 400, "serif-400"), ("Instrument Serif", "italic", 400, "serif-400i"),
         ("Geist", "normal", 400, "sans-400"), ("Geist", "normal", 500, "sans-500"),
         ("Geist", "normal", 600, "sans-600"), ("Geist Mono", "normal", 400, "mono-400"),
         ("Geist Mono", "normal", 500, "mono-500")]
_font_cache, _metric_cache = {}, {}


def font_css(*keys):
    out = []
    for fam, style, w, key in FACES:
        if key not in keys:
            continue
        for suffix, rng in (("", "U+0000-00FF,U+2000-21FF"), ("-ext", "U+0100-024F")):
            f = FONTS / f"{key}{suffix}.woff"
            if not f.exists():
                continue
            b64 = _font_cache.setdefault(f, base64.b64encode(f.read_bytes()).decode())
            out.append(f"@font-face{{font-family:'{fam}';font-style:{style};font-weight:{w};"
                       f"unicode-range:{rng};src:url(data:font/woff;base64,{b64}) format('woff')}}")
    return "".join(out)


def text_width(text, key, size):
    """Measure text with the real font metrics (fontTools)."""
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return len(text) * size * 0.56
    if key not in _metric_cache:
        fonts = [TTFont(FONTS / f"{key}{s}.woff") for s in ("", "-ext") if (FONTS / f"{key}{s}.woff").exists()]
        _metric_cache[key] = [(f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm) for f in fonts]
    total = 0.0
    for ch in text:
        for cmap, hmtx, upm in _metric_cache[key]:
            if ord(ch) in cmap:
                total += hmtx[cmap[ord(ch)]][0] / upm
                break
        else:
            total += 0.5
    return total * size


def esc(s):
    return html.escape(str(s), quote=True)


BASE_CSS = """
.serif{font-family:'Instrument Serif',Georgia,serif}
.sans{font-family:'Geist',-apple-system,'Segoe UI',Helvetica,Arial,sans-serif}
.mono{font-family:'Geist Mono',ui-monospace,SFMono-Regular,Menlo,monospace}
.rise{animation:rise .9s cubic-bezier(.2,.8,.2,1) backwards}
@keyframes rise{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:none}}
.fade{animation:fade .6s ease backwards}
@keyframes fade{from{opacity:0}to{opacity:1}}
.pop{transform-box:fill-box;transform-origin:center;animation:pop .45s cubic-bezier(.3,1.6,.5,1) backwards}
@keyframes pop{from{opacity:0;transform:scale(0)}to{opacity:1;transform:scale(1)}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""


def svg(w, h, body, css="", fonts=(), label=""):
    static = "*{animation:none!important}" if STATIC else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{esc(label)}"><style>{font_css(*fonts)}{BASE_CSS}{css}{static}</style>'
            f'{body}</svg>')


def frame(w, h, fill=PAPER):
    return f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="16" fill="{fill}" stroke="{LINE}" stroke-width="1.5"/>'


def d(s):
    return f"animation-delay:{s:.3f}s"


# ───────────────────────── data ─────────────────────────
def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": "readme-cards"})
    if TOKEN and "api.github.com" in url:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    return raw if binary else raw.decode("utf-8")


def fetch_contributions():
    page = get(f"https://github.com/users/{USER}/contributions")
    tips = {m.group(1): m.group(2) for m in re.finditer(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page)}
    days = []
    for m in re.finditer(r'<td[^>]*class="ContributionCalendar-day"[^>]*>', page):
        tag = m.group(0)
        date = re.search(r'data-date="([\d-]+)"', tag)
        if not date:
            continue
        ident = re.search(r'id="([^"]+)"', tag)
        level = int(re.search(r'data-level="(\d)"', tag).group(1))
        tip = tips.get(ident.group(1) if ident else "", "")
        n = re.match(r"\s*(\d+)", tip)
        days.append({"date": date.group(1), "count": int(n.group(1)) if n else 0, "level": level})
    if len(days) < 300:
        raise RuntimeError("could not parse contribution calendar")
    days.sort(key=lambda x: x["date"])
    total = re.search(r"([\d,]+)\s+contributions?\s+in the last year", page)
    return {"user": USER, "updated": dt.date.today().isoformat(),
            "total": int(total.group(1).replace(",", "")) if total else sum(x["count"] for x in days),
            "days": days}


def fetch_profile():
    user = json.loads(get(f"https://api.github.com/users/{USER}"))
    repos = json.loads(get(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner"))
    return {"public_repos": user.get("public_repos", 0), "followers": user.get("followers", 0),
            "repos": {r["name"]: {"description": r.get("description"), "language": r.get("language"),
                                  "stars": r.get("stargazers_count", 0), "fork": r.get("fork")} for r in repos}}


def cached(name, fn, default):
    path = DATA / name
    if not OFFLINE:
        try:
            data = fn()
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1))
            return data
        except Exception as e:  # keep yesterday's data if GitHub hiccups
            print(f"warn: {name}: {e}")
    return json.loads(path.read_text()) if path.exists() else default


def photo_data_uri():
    """assets/photo.jpg|png wins; otherwise the GitHub avatar (cached in assets/avatar.png)."""
    src = next((p for p in (ASSETS / "photo.jpg", ASSETS / "photo.jpeg", ASSETS / "photo.png") if p.exists()), None)
    if src is None:
        src = ASSETS / "avatar.png"
        if not OFFLINE:
            try:
                src.write_bytes(get(f"https://github.com/{USER}.png?size=600", binary=True))
            except Exception as e:
                print(f"warn: avatar: {e}")
    if not src.exists():
        return None
    try:
        from PIL import Image, ImageOps
        im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
        im = ImageOps.fit(im, (560, 560), Image.LANCZOS, centering=(0.5, 0.4))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=84, optimize=True, progressive=True)
        raw, mime = buf.getvalue(), "image/jpeg"
    except ImportError:
        raw, mime = src.read_bytes(), "image/png" if src.suffix == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


# ───────────────────────── stats ─────────────────────────
def stats(c):
    days = c["days"]
    active = [x for x in days if x["count"] > 0]
    longest = run = 0
    for x in days:
        run = run + 1 if x["count"] else 0
        longest = max(longest, run)
    current = 0
    tail = days[:-1] if days and days[-1]["count"] == 0 else days  # today may still be empty
    for x in reversed(tail):
        if not x["count"]:
            break
        current += 1
    busiest = max(days, key=lambda x: x["count"]) if days else {"date": "", "count": 0}
    months = {}
    for x in days:
        months[x["date"][:7]] = months.get(x["date"][:7], 0) + x["count"]
    return {"total": c.get("total") or sum(x["count"] for x in days), "active": len(active),
            "longest": longest, "current": current, "busiest": busiest, "months": months}


def nice_date(iso, fmt="%d %b"):
    return dt.date.fromisoformat(iso).strftime(fmt).lstrip("0") if iso else ""


# ───────────────────────── cards ─────────────────────────
def hero(photo):
    W, H = 900, 340
    P = 36  # photo position / size
    PS = H - 2 * P
    strips = 24
    css = f"""
.strip{{animation:unveil .35s ease backwards}}
@keyframes unveil{{from{{opacity:1}}to{{opacity:0}}}}
.strip{{opacity:0}}
.shine{{opacity:0;animation:shine 4.5s ease-in-out 2.2s infinite}}
@keyframes shine{{0%{{opacity:.85;transform:translateX(-140px)}}35%{{opacity:.85;transform:translateX(330px)}}36%,100%{{opacity:0;transform:translateX(330px)}}}}
.dot{{transform-box:fill-box;transform-origin:center;animation:pulse 1.8s ease-out 1.6s infinite}}
@keyframes pulse{{0%{{opacity:.6;transform:scale(1)}}100%{{opacity:0;transform:scale(3.2)}}}}
.dot{{opacity:0}}
.cursor{{animation:blink 1s steps(1) infinite}}
@keyframes blink{{50%{{opacity:0}}}}
"""
    body = [frame(W, H)]
    # photo with a row-by-row "print-in" reveal
    body.append(f'<defs><clipPath id="ph"><rect x="{P}" y="{P}" width="{PS}" height="{PS}" rx="12"/></clipPath>'
                f'<linearGradient id="sh" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
                f'<stop offset=".5" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient></defs>')
    ascii_rows = None
    art = ASSETS / "portrait.txt"
    if PORTRAIT == "ascii" and art.exists():
        ascii_rows = art.read_text(encoding="utf-8").rstrip("\n").split("\n")
    if ascii_rows:
        # ASCII portrait that prints in row by row, like a slow terminal
        cols = max(len(r) for r in ascii_rows)
        n = len(ascii_rows)
        pad = 10
        cw = (PS - 2 * pad) / cols
        lh = (PS - 2 * pad) / n
        fs = cw / (text_width("M", "mono-400", 1) or 0.6)
        body.append(f'<defs><linearGradient id="pg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{INK}"/>'
                    f'<stop offset=".55" stop-color="{INK}"/><stop offset="1" stop-color="#8FA7FF"/></linearGradient></defs>')
        body.append(f'<rect x="{P}" y="{P}" width="{PS}" height="{PS}" rx="12" fill="{DEEP}"/>')
        body.append(f'<g class="mono" font-size="{fs:.2f}" fill="url(#pg)">')
        for i, row in enumerate(ascii_rows):
            if not row.strip():
                continue
            body.append(f'<text class="fade" style="{d(0.15 + i*0.018)};animation-duration:.25s" x="{P+pad}" y="{P + pad + (i+0.8)*lh:.2f}" '
                        f'xml:space="preserve" textLength="{len(row)*cw:.2f}" lengthAdjust="spacingAndGlyphs">{esc(row)}</text>')
        body.append("</g>")
    else:
        body.append(f'<g clip-path="url(#ph)">')
        if photo:
            body.append(f'<image href="{photo}" x="{P}" y="{P}" width="{PS}" height="{PS}" preserveAspectRatio="xMidYMid slice"/>')
        else:
            body.append(f'<rect x="{P}" y="{P}" width="{PS}" height="{PS}" fill="{LINE}"/>'
                        f'<circle cx="{P+PS/2}" cy="{P+PS*0.4}" r="{PS*0.17}" fill="{MUTED}"/>'
                        f'<ellipse cx="{P+PS/2}" cy="{P+PS*0.98}" rx="{PS*0.36}" ry="{PS*0.3}" fill="{MUTED}"/>')
        sh = PS / strips
        for i in range(strips):
            body.append(f'<rect class="strip" style="{d(0.15 + i*0.035)}" x="{P}" y="{P + i*sh - 0.5:.2f}" '
                        f'width="{PS}" height="{sh + 1:.2f}" fill="{DEEP}"/>')
        body.append("</g>")
    body.append(f'<rect x="{P}" y="{P}" width="{PS}" height="{PS}" rx="12" fill="none" stroke="{LINE}" stroke-width="1.5"/>')
    # sticker
    body.append(f'<g class="pop" style="{d(1.2)}"><g transform="rotate(-8 {P+PS-18} {P+PS-14})">'
                f'<rect x="{P+PS-64}" y="{P+PS-30}" width="92" height="30" rx="15" fill="{YELLOW}" stroke="{DEEP}" stroke-width="1.5"/>'
                f'<text x="{P+PS-18}" y="{P+PS-10}" text-anchor="middle" class="mono" font-size="12" font-weight="500" fill="{DEEP}">@{esc(USER.lower())}</text></g></g>')

    X = P + PS + 40
    body.append(f'<text class="mono rise" style="{d(0.2)}" x="{X}" y="74" font-size="12" letter-spacing="2.4" fill="{MUTED}">'
                f'{esc(EYEBROW)}<tspan class="cursor" fill="{BLUE}"> _</tspan></text>')
    body.append(f'<text class="serif rise" style="{d(0.35)}" x="{X}" y="134" font-size="62" fill="{INK}">{esc(FIRST)}</text>')
    body.append(f'<defs><clipPath id="nm"><text x="{X}" y="194" font-size="62" font-style="italic" '
                f'font-family="Instrument Serif,Georgia,serif">{esc(LAST)}.</text></clipPath></defs>')
    body.append(f'<g class="rise" style="{d(0.5)}"><text class="serif" x="{X}" y="194" font-size="62" font-style="italic" fill="{BLUE}">{esc(LAST)}.</text>'
                f'<g clip-path="url(#nm)"><rect class="shine" x="{X - 40}" y="140" width="90" height="70" fill="url(#sh)" transform="skewX(-18)"/></g></g>')
    for i, line in enumerate(BIO):
        body.append(f'<text class="sans rise" style="{d(0.7 + i*0.12)}" x="{X}" y="{232 + i*24}" font-size="15.5" fill="{INK}" fill-opacity=".78">{esc(line)}</text>')
    body.append(f'<text class="mono rise" style="{d(1.0)}" x="{X}" y="298" font-size="12" letter-spacing="1.6" fill="{MUTED}">'
                f'<tspan fill="{BLUE}">●</tspan>  {esc(LOCATION.upper())}</text>')
    return svg(W, H, "".join(body), css, ("serif-400", "serif-400i", "sans-400", "sans-500", "mono-400", "mono-500"),
               f"{FIRST} {LAST}")


def graph(c, s):
    W, H = 900, 210
    days = c["days"]
    first = dt.date.fromisoformat(days[0]["date"])
    offset = (first.weekday() + 1) % 7  # Sunday-first rows like GitHub
    weeks = (len(days) + offset + 6) // 7
    cell, gap = 12, 3
    gx = (W - (weeks * (cell + gap) - gap)) / 2
    gy = 84
    body = [frame(W, H)]
    body.append(f'<text class="serif rise" style="{d(0.6)}" x="{gx:.1f}" y="50" font-size="28" fill="{INK}">'
                f'{s["total"]:,} contributions <tspan font-style="italic" fill="{BLUE}">in the last year</tspan></text>')
    upd = f'updated {nice_date(c.get("updated", days[-1]["date"]), "%d %b %Y")}'
    body.append(f'<text class="mono fade" style="{d(0.8)}" x="{W - gx - text_width(upd, "mono-400", 11):.1f}" y="48" font-size="11" fill="{MUTED}">{upd}</text>')
    seen = set()
    for i, x in enumerate(days):
        k = i + offset
        col, row = divmod(k, 7)
        dd = dt.date.fromisoformat(x["date"])
        if dd.day <= 7 and row == 0 and dd.strftime("%b%y") not in seen and col < weeks - 1:
            seen.add(dd.strftime("%b%y"))
            body.append(f'<text class="mono fade" style="{d(0.8)}" x="{gx + col*(cell+gap):.1f}" y="{gy-8}" font-size="10" fill="{MUTED}">{dd.strftime("%b")}</text>')
        body.append(f'<rect class="pop" style="{d(0.8 + col*0.022 + row*0.01)}" x="{gx + col*(cell+gap):.1f}" y="{gy + row*(cell+gap)}" '
                    f'width="{cell}" height="{cell}" rx="3" fill="{GRAPH[x["level"]]}"><title>{x["count"]} on {x["date"]}</title></rect>')
    return svg(W, H, "".join(body), "", ("serif-400", "serif-400i", "mono-400"), f'{s["total"]} contributions in the last year')


def months_card(s):
    W, H = 900, 320
    items = list(s["months"].items())
    best = max(items, key=lambda kv: kv[1]) if items else ("", 0)
    top = max(best[1], 1)
    x0, x1, base, hmax = 40, 590, 262, 150
    slot = (x1 - x0) / max(len(items), 1)
    bw = min(28, slot * 0.6)
    css = """
.bar{transform-box:fill-box;transform-origin:bottom;animation:grow .7s cubic-bezier(.2,.9,.25,1.1) backwards}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
"""
    body = [frame(W, H)]
    body.append(f'<text class="serif rise" style="{d(1.4)}" x="{x0}" y="56" font-size="28" fill="{INK}">Month by month</text>')
    body.append(f'<line x1="{x0}" y1="{base}" x2="{x1}" y2="{base}" stroke="{MUTED}" stroke-width="1.2"/>')
    for i, (m, v) in enumerate(items):
        cx = x0 + slot * (i + 0.5)
        h = max(2, v / top * hmax) if v else 2
        isbest = m == best[0]
        delay = 1.6 + i * 0.06
        body.append(f'<rect class="bar" style="{d(delay)}" x="{cx - bw/2:.1f}" y="{base - h:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="4" '
                    f'fill="{BLUE if isbest else (BAR if v else LINE)}"><title>{v} in {m}</title></rect>')
        lab = dt.date.fromisoformat(m + "-01").strftime("%b")
        body.append(f'<text class="mono fade" style="{d(1.6)}" x="{cx:.1f}" y="{base + 20}" text-anchor="middle" font-size="10.5" fill="{INK if isbest else MUTED}">{lab}</text>')
        if isbest:
            body.append(f'<g class="pop" style="{d(delay + 0.75)}"><rect x="{cx-22:.1f}" y="{base-h-34:.1f}" width="44" height="24" rx="12" fill="{BLUE}"/>'
                        f'<text class="mono" x="{cx:.1f}" y="{base-h-17.5:.1f}" text-anchor="middle" font-size="12" font-weight="500" fill="#fff">{v}</text></g>')
    # stats column
    bx = 630
    body.append(f'<line x1="{bx-10}" y1="36" x2="{bx-10}" y2="{H-36}" stroke="{LINE}" stroke-width="1.2"/>')
    rows = [("LONGEST STREAK", f'{s["longest"]}', "days"),
            ("CURRENT STREAK", f'{s["current"]}', "days"),
            ("ACTIVE DAYS", f'{s["active"]}', "this year"),
            ("BUSIEST DAY", f'{s["busiest"]["count"]}', nice_date(s["busiest"]["date"]))]
    for i, (k, v, unit) in enumerate(rows):
        y = 70 + i * 62
        delay = 1.8 + i * 0.12
        body.append(f'<g class="rise" style="{d(delay)}"><text class="mono" x="{bx+14}" y="{y}" font-size="10.5" letter-spacing="1.6" fill="{MUTED}">{k}</text>'
                    f'<text class="serif" x="{bx+14}" y="{y+36}" font-size="38" fill="{BLUE if i == 0 else INK}">{v}'
                    f'<tspan class="sans" font-size="13" fill="{MUTED}" dx="8">{esc(unit)}</tspan></text></g>')
    return svg(W, H, "".join(body), css, ("serif-400", "sans-400", "mono-400", "mono-500"), "Contributions per month")


def tile(idx, label, bg, fg, value=None, caption="", big=None, cta="", delay=2.4):
    W, H = 300, 320
    M = 10
    css = f"""
.tile{{transform-box:fill-box;transform-origin:50% 100%;animation:swing 1.1s cubic-bezier(.2,.9,.25,1) {delay}s backwards}}
@keyframes swing{{0%{{opacity:0;transform:translateY(70px) rotate(-7deg)}}60%{{opacity:1;transform:translateY(-8px) rotate(1.5deg)}}80%{{transform:translateY(2px) rotate(-.4deg)}}100%{{transform:none}}}}
.ring{{opacity:0;transform-box:fill-box;transform-origin:center;animation:ring 3.2s ease-out {delay+1.2}s infinite}}
@keyframes ring{{0%{{opacity:.7;transform:scale(.4)}}45%,100%{{opacity:0;transform:scale(2.6)}}}}
.gl{{opacity:0;animation:gl 5s ease-in-out {delay+1.6}s infinite}}
@keyframes gl{{0%{{opacity:.55;transform:translateX(-200px)}}30%{{opacity:.55;transform:translateX(420px)}}31%,100%{{opacity:0}}}}
.arrow{{animation:nudge 1.6s ease-in-out {delay+1.4}s infinite}}
@keyframes nudge{{0%,100%{{transform:none}}50%{{transform:translate(4px,-4px)}}}}
.f{{opacity:0;animation:flash .05s linear}}
@keyframes flash{{0%,100%{{opacity:1}}}}
.fin{{animation:fade .01s linear backwards}}
"""
    b = [f'<defs><clipPath id="t"><rect x="{M}" y="{M}" width="{W-2*M}" height="{H-2*M}" rx="18"/></clipPath>'
         f'<linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".8"/>'
         f'<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient></defs>']
    b.append(f'<g class="tile"><rect x="{M}" y="{M}" width="{W-2*M}" height="{H-2*M}" rx="18" fill="{bg}" stroke="{DEEP}" stroke-width="1.5"/>')
    b.append(f'<g clip-path="url(#t)"><circle class="ring" cx="{W-M-34}" cy="{M+34}" r="22" fill="none" stroke="{fg}" stroke-width="2"/>'
             f'<rect class="gl" x="{M-60}" y="{M-20}" width="80" height="{H+40}" fill="url(#g)" transform="skewX(-16)"/></g>')
    b.append(f'<text class="mono" x="{M+24}" y="{M+40}" font-size="12" letter-spacing="2" fill="{fg}" fill-opacity=".85">{idx:02d} / {label}</text>')
    b.append(f'<circle cx="{W-M-34}" cy="{M+34}" r="6" fill="{fg}"/>')
    if value is not None:
        start, n, step = delay + 0.55, 18, 0.05
        for k in range(n):
            v = round(value * (1 - (1 - k / n) ** 3))
            b.append(f'<text class="serif f" style="{d(start + k*step)}" x="{M+22}" y="{M+178}" font-size="100" fill="{fg}">{v}</text>')
        b.append(f'<text class="serif fin" style="{d(start + n*step)}" x="{M+22}" y="{M+178}" font-size="100" fill="{fg}">{value}</text>')
    elif big:
        for i, line in enumerate(big):
            b.append(f'<text class="serif" x="{M+22}" y="{M+128 + i*58}" font-size="62" fill="{fg}" font-style="{"italic" if i else "normal"}">{esc(line)}</text>')
    b.append(f'<text class="sans" x="{M+24}" y="{M+214}" font-size="15" fill="{fg}" fill-opacity=".85">{esc(caption)}</text>')
    b.append(f'<line x1="{M+24}" y1="{H-M-68}" x2="{W-M-24}" y2="{H-M-68}" stroke="{fg}" stroke-opacity=".35"/>')
    b.append(f'<text class="sans" x="{M+24}" y="{H-M-34}" font-size="15" font-weight="600" fill="{fg}">{esc(cta)}</text>')
    b.append(f'<g class="arrow"><text class="sans" x="{W-M-44}" y="{H-M-32}" font-size="22" font-weight="600" fill="{fg}">↗</text></g></g>')
    return svg(W, H, "".join(b), css, ("serif-400", "serif-400i", "sans-400", "sans-600", "mono-400"), f"{label} {value or ''}")


def wrap(text, key, size, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if text_width(t, key, size) > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    if len(lines) > 2:
        lines = lines[:2]
        lines[1] = lines[1].rstrip(".,") + "…"
    return lines


def repo_card(i, name, desc, lang, stars, delay):
    W, H = 440, 190
    accent = [BLUE, RED, YELLOW, MUTED][i % 4]
    size = 34
    while text_width(name, "serif-400", size) > W - 110 and size > 20:
        size -= 1
    css = """
.card{animation:up .8s cubic-bezier(.2,.8,.2,1) backwards}
@keyframes up{from{opacity:0;transform:translateY(26px)}to{opacity:1;transform:none}}
.arrow{animation:nudge 1.6s ease-in-out 5s infinite}
@keyframes nudge{0%,100%{transform:none}50%{transform:translate(4px,-4px)}}
"""
    b = [f'<g class="card" style="{d(delay)}">{frame(W, H)}',
         f'<path d="M1 17 V17 a16 16 0 0 1 16 -16 H{W-17} a16 16 0 0 1 16 16 V17 Z" fill="{accent}"/>',
         f'<line x1="1" y1="17" x2="{W-1}" y2="17" stroke="{LINE}" stroke-width="1.5"/>',
         f'<text class="mono" x="26" y="48" font-size="11" letter-spacing="1.6" fill="{MUTED}">REPO / {i+1:02d}</text>',
         f'<text class="serif" x="26" y="88" font-size="{size}" fill="{INK}">{esc(name)}</text>',
         f'<g class="arrow"><text class="sans" x="{W-46}" y="52" font-size="20" font-weight="600" fill="{INK}">↗</text></g>']
    for k, line in enumerate(wrap(desc or "", "sans-400", 14, W - 52)):
        b.append(f'<text class="sans" x="26" y="{118 + k*20}" font-size="14" fill="{INK}" fill-opacity=".72">{esc(line)}</text>')
    b.append(f'<circle cx="32" cy="{H-26}" r="5.5" fill="{LANG.get(lang, MUTED)}" stroke="{DEEP}" stroke-width=".8"/>'
             f'<text class="mono" x="44" y="{H-22}" font-size="12" fill="{INK}">{esc(lang or "—")}</text>')
    if stars:
        st = f"★ {stars}"
        b.append(f'<text class="mono" x="{W-26-text_width(st, "mono-400", 12):.1f}" y="{H-22}" font-size="12" fill="{MUTED}">{st}</text>')
    b.append("</g>")
    return svg(W, H, "".join(b), css, ("serif-400", "sans-400", "sans-600", "mono-400"), f"{name}: {desc}")


def stack_card():
    W = 900
    fs, padx, h, gapx, gapy = 14, 16, 34, 10, 12
    x, y, rows = 36, 84, []
    chips = []
    for name in STACK:
        w = text_width(name, "sans-500", fs) + 2 * padx
        if x + w > W - 36:
            x, y = 36, y + h + gapy
        chips.append((name, x, y, w))
        x += w + gapx
    H = y + h + 36
    css = ".cursor{animation:blink 1s steps(1) infinite}@keyframes blink{50%{opacity:0}}"
    b = [frame(W, H),
         f'<text class="serif rise" style="{d(3.6)}" x="36" y="56" font-size="28" fill="{INK}">What I’m coding with'
         f'<tspan class="cursor" fill="{BLUE}"> ▍</tspan></text>']
    colors = [BLUE, RED, YELLOW]
    for i, (name, cx, cy, w) in enumerate(chips):
        b.append(f'<g class="pop" style="{d(3.8 + i*0.07)}"><rect x="{cx:.1f}" y="{cy}" width="{w:.1f}" height="{h}" rx="{h/2}" fill="{CHIP}" stroke="{LINE}" stroke-width="1.2"/>'
                 f''
                 f'<text class="sans" x="{cx + w/2:.1f}" y="{cy + h/2 + 5}" text-anchor="middle" font-size="{fs}" font-weight="500" fill="{INK}">{esc(name)}</text></g>')
    return svg(W, H, "".join(b), css, ("serif-400", "sans-500"), "Tech stack: " + ", ".join(STACK))


# ───────────────────────── main ─────────────────────────
def main():
    CARDS.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    contrib = cached("contributions.json", fetch_contributions, None)
    profile = cached("profile.json", fetch_profile, {"public_repos": 28, "followers": 0, "repos": {}})
    s = stats(contrib)
    out = {
        "hero.svg": hero(photo_data_uri()),
        "graph.svg": graph(contrib, s),
        "months.svg": months_card(s),
        "build.svg": tile(1, "BUILD", TILE_BLUE, "#FFFFFF", value=profile.get("public_repos") or 28,
                          caption="public repositories", cta="See my projects", delay=2.4),
        "ship.svg": tile(2, "SHIP", TILE_RED, "#FFFFFF", value=s["total"],
                         caption="contributions this year", cta="Follow on GitHub", delay=2.55),
        "connect.svg": tile(3, "CONNECT", TILE_YELLOW, DEEP, big=["Let’s", "talk."],
                            caption="in/melik-kutlay-atilla", cta="Say hi on LinkedIn", delay=2.7),
        "stack.svg": stack_card(),
    }
    for i, (name, desc, lang) in enumerate(FEATURED):
        r = profile.get("repos", {}).get(name, {})
        out[f"repo-{i+1}.svg"] = repo_card(i, name, r.get("description") or desc, r.get("language") or lang,
                                           r.get("stars", 0), 3.0 + i * 0.12)
    for fn, content in out.items():
        (CARDS / fn).write_text(content, encoding="utf-8")
    print(f"rendered {len(out)} cards · {s['total']} contributions · best month "
          f"{max(s['months'], key=s['months'].get)} · longest streak {s['longest']}")


if __name__ == "__main__":
    main()
