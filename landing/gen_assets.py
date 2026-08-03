from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

BASE = Path(__file__).parent / 'assets'
BASE.mkdir(parents=True, exist_ok=True)

NAVY = '#0a1f4d'
GOLD = '#d9a441'
WHITE = '#ffffff'

def rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def make_icon(size, fg, bg, letter, filename):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size-1, size-1], radius=int(size*0.22), fill=bg)
    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(size*0.5))
    bbox = d.textbbox((0, 0), letter, font=font)
    w, h = bbox[2]-bbox[0], bbox[3]-bbox[1]
    d.text(((size-w)/2-bbox[0], (size-h)/2-bbox[1]), letter, font=font, fill=fg)
    img.save(BASE / filename)

make_icon(512, rgb(NAVY), rgb(GOLD), 'S', 'logo-512.png')
make_icon(192, rgb(NAVY), rgb(GOLD), 'S', 'logo-192.png')
make_icon(180, rgb(NAVY), rgb(GOLD), 'S', 'apple-touch-icon.png')
make_icon(64, rgb(WHITE), rgb(NAVY), 'S', 'mark-nav.png')
make_icon(48, rgb(GOLD), rgb(NAVY), 'S', 'mark-sm.png')
print("OK:", sorted(p.name for p in BASE.iterdir()))
