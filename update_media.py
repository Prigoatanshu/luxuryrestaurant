from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(r"c:\luxury restaurant")
SITE = ROOT / "site"
INDEX = SITE / "index.html"
MEDIA = SITE / "media"
DISH_DIR = MEDIA / "dishes"
html = INDEX.read_text(encoding="utf-8")
pattern = re.compile(r"<article class=\"menu-item reveal\">(.*?)</article>", re.S)
blocks = pattern.findall(html)
if not blocks:
    raise SystemExit("No menu items found in index.html")

DISH_DIR.mkdir(parents=True, exist_ok=True)

palette = [
    ("#1f1410", "#b07a45"),
    ("#1a1512", "#c79a63"),
    ("#171411", "#9f7a52"),
    ("#120f0c", "#d1a878"),
    ("#221812", "#b88954"),
    ("#1b1512", "#d8b27a"),
]

used = set()
image_files = []
new_blocks = []
for idx, block in enumerate(blocks, start=1):
    match = re.search(r"<h3>(.*?)</h3>", block)
    if not match:
        raise SystemExit("Menu item missing <h3> title")
    name = match.group(1).strip()
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if slug in used:
        suffix = 2
        while f"{slug}-{suffix}" in used:
            suffix += 1
        slug = f"{slug}-{suffix}"
    used.add(slug)
    filename = f"{idx:02d}-{slug}.svg"
    image_files.append(filename)
    if "menu-photo" not in block:
        parts = block.split("</div>", 1)
        if len(parts) != 2:
            raise SystemExit("Unexpected menu item markup")
        img = f"  <img class=\"menu-photo\" src=\"media/dishes/{filename}\" alt=\"{name}\">\n"
        block = parts[0] + "</div>\n" + img + parts[1]

    new_blocks.append(block)
new_html = html
for old, new in zip(blocks, new_blocks):
    new_html = new_html.replace(old, new, 1)

INDEX.write_text(new_html, encoding="utf-8")
for idx, filename in enumerate(image_files, start=1):
    name_match = re.search(r"\d{2}-(.*)\.svg", filename)
    label = name_match.group(1).replace("-", " ").title() if name_match else "Signature Dish"
    c1, c2 = palette[(idx - 1) % len(palette)]
    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='800' viewBox='0 0 1200 800'>
  <defs>
    <linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>
      <stop offset='0' stop-color='{c1}'/>
      <stop offset='1' stop-color='{c2}'/>
    </linearGradient>
  </defs>
  <rect width='1200' height='800' fill='url(#g)'/>
  <rect width='1200' height='800' fill='rgba(0,0,0,0.25)'/>
  <text x='70' y='140' fill='#F6EFE6' font-family='Cormorant Garamond, serif' font-size='64' letter-spacing='2'>{label}</text>
  <text x='70' y='210' fill='#C7B9AB' font-family='Manrope, sans-serif' font-size='24' letter-spacing='6'>SIGNATURE DISH</text>
</svg>
"""
    (DISH_DIR / filename).write_text(svg, encoding="utf-8")
MEDIA.mkdir(parents=True, exist_ok=True)
poster1 = MEDIA / "restaurant-poster.svg"
poster2 = MEDIA / "kitchen-poster.svg"

poster_svg = """<svg xmlns='http://www.w3.org/2000/svg' width='1600' height='900' viewBox='0 0 1600 900'>
  <defs>
    <linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>
      <stop offset='0' stop-color='#1b140f'/>
      <stop offset='1' stop-color='#c79a63'/>
    </linearGradient>
  </defs>
  <rect width='1600' height='900' fill='url(#g)'/>
  <rect width='1600' height='900' fill='rgba(0,0,0,0.35)'/>
  <text x='80' y='140' fill='#F6EFE6' font-family='Cormorant Garamond, serif' font-size='72' letter-spacing='3'>Maison Ember</text>
  <text x='80' y='210' fill='#C7B9AB' font-family='Manrope, sans-serif' font-size='26' letter-spacing='6'>RESTAURANT TOUR</text>
</svg>
"""

poster_svg_2 = """<svg xmlns='http://www.w3.org/2000/svg' width='1600' height='900' viewBox='0 0 1600 900'>
  <defs>
    <linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>
      <stop offset='0' stop-color='#15110e'/>
      <stop offset='1' stop-color='#b88954'/>
    </linearGradient>
  </defs>
  <rect width='1600' height='900' fill='url(#g)'/>
  <rect width='1600' height='900' fill='rgba(0,0,0,0.35)'/>
  <text x='80' y='140' fill='#F6EFE6' font-family='Cormorant Garamond, serif' font-size='68' letter-spacing='3'>Chef Studio</text>
  <text x='80' y='210' fill='#C7B9AB' font-family='Manrope, sans-serif' font-size='26' letter-spacing='6'>BEHIND THE PASS</text>
</svg>
"""

poster1.write_text(poster_svg, encoding="utf-8")
poster2.write_text(poster_svg_2, encoding="utf-8")

readme = MEDIA / "README.txt"
readme.write_text(
    "Drop your real MP4 videos here and name them:\n"
    "- restaurant-tour.mp4\n"
    "- chef-studio.mp4\n",
    encoding="utf-8",
)

print("Updated menu items with images and generated placeholders.")
