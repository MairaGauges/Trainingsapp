"""App-Icons: dunkelblauer Hintergrund mit großem weißem T (ohne Schriftdatei gezeichnet)."""
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "web", "icons")
BLUE = "#0b2545"
WHITE = "#ffffff"


def icon(size):
    s = size * 4  # supersampling für glatte Kanten
    img = Image.new("RGB", (s, s), BLUE)
    d = ImageDraw.Draw(img)
    # T liegt in der sicheren Zone (mittlere 80 %), damit Android-Masken nichts abschneiden
    bar_w, bar_h, stem_w = 0.56 * s, 0.13 * s, 0.15 * s
    top, bottom = 0.24 * s, 0.76 * s
    r = 0.025 * s
    d.rounded_rectangle([(s - bar_w) / 2, top, (s + bar_w) / 2, top + bar_h], r, fill=WHITE)
    d.rounded_rectangle([(s - stem_w) / 2, top, (s + stem_w) / 2, bottom], r, fill=WHITE)
    return img.resize((size, size), Image.LANCZOS)


os.makedirs(OUT, exist_ok=True)
for n in (180, 192, 512):
    icon(n).save(os.path.join(OUT, f"icon-{n}.png"), optimize=True)
print("icons ok")
