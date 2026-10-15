#!/usr/bin/env python3
"""Render a transparent 'new warm lead' card that pops up (RGBA PNG sequence -> lead_card.mov, qtrle with alpha)."""
import os, subprocess, tempfile, math
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS, DUR = 768, 1344, 24, 3.6
B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"; R = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
GOLD, GREEN, NAVY = (255, 205, 60), (60, 200, 110), (14, 26, 50)
def ease(x): x = max(0., min(1., x)); return 1 - (1 - x) ** 3
def frame(t, ox, oy):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    p = ease((t - 0.35) / 0.5)
    if p <= 0: return im
    s = 0.3 + 0.7 * p + 0.08 * math.sin(math.pi * min(1, (t - 0.35) / 0.5)) * (1 - p)
    tx, ty = W / 2, 300
    cx, cy = ox + (tx - ox) * p, oy + (ty - oy) * p          # flies out of the monitor up to top-centre
    cw, ch = 600 * s, 250 * s
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(card)
    d.rounded_rectangle([cx - cw / 2 + 8, cy - ch / 2 + 12, cx + cw / 2 + 8, cy + ch / 2 + 12], radius=28 * s, fill=(0, 0, 0, 120))
    d.rounded_rectangle([cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2], radius=28 * s, fill=(255, 255, 255, 250), outline=GOLD, width=max(2, int(6 * s)))
    if s > 0.85:
        x0, y0 = cx - cw / 2, cy - ch / 2
        d.rounded_rectangle([x0 + 28, y0 + 26, x0 + 300, y0 + 74], radius=24, fill=GREEN)
        d.text((x0 + 164, y0 + 50), "NEW WARM LEAD", font=ImageFont.truetype(B, 24), fill=(255, 255, 255), anchor="mm")
        d.text((x0 + 30, y0 + 116), "Sarah Mitchell", font=ImageFont.truetype(B, 44), fill=NAVY, anchor="lm")
        d.text((x0 + 30, y0 + 172), "Ready to buy  ·  Lease ends Dec", font=ImageFont.truetype(R, 26), fill=(80, 92, 115), anchor="lm")
        d.text((x0 + 30, y0 + 210), "Wants a bigger SUV  ·  Call today", font=ImageFont.truetype(R, 26), fill=(80, 92, 115), anchor="lm")
    return card
def main():
    ox, oy = float(os.environ.get("OX", 520)), float(os.environ.get("OY", 700))
    tmp = tempfile.mkdtemp()
    for k in range(int(DUR * FPS)):
        frame(k / FPS, ox, oy).save(os.path.join(tmp, f"f{k:04d}.png"))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(tmp, "f%04d.png"),
                    "-c:v", "qtrle", "-pix_fmt", "argb", os.path.join(HERE, "anim", "lead_card.mov")], check=True)
    bg = Image.new("RGBA", (W, H), (60, 80, 110, 255)); bg.alpha_composite(frame(2.5, ox, oy)); bg.convert("RGB").resize((W // 3, H // 3)).save(os.path.join(HERE, "anim", "lead_preview.png"))
if __name__ == "__main__":
    main()
