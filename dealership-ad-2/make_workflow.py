#!/usr/bin/env python3
"""Render an animated 9:16 'AI marketing workflow' diagram (exact text) to workflow_diagram.mp4."""
import math, os, subprocess, tempfile
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS, DUR = 768, 1344, 24, 6.0
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BG1, BG2 = (6, 16, 38), (10, 34, 64)
TEAL, GOLD, WHITE, MUTED = (45, 212, 191), (255, 213, 74), (240, 246, 252), (150, 175, 200)

STEPS = [
    ("CUSTOMER DATABASE", "Your CRM: every customer & vehicle", TEAL),
    ("AI FINDS OPPORTUNITIES", "Due for service • Tires • Ready to buy", TEAL),
    ("PERSONALIZED OFFER", "Free tire rotation + brake inspection", GOLD),
    ("AUTOMATED OUTREACH", "Text • Email • AI phone call", TEAL),
    ("APPOINTMENT BOOKED", "Customer comes back in", TEAL),
    ("REVENUE GROWS", "Service • Parts • Sales", GOLD),
]
TOP, BOX_H, GAP, BOX_W = 250, 132, 46, 620
X0 = (W - BOX_W) // 2
f_title = ImageFont.truetype(BOLD, 40)
f_sub = ImageFont.truetype(REG, 24)
f_head = ImageFont.truetype(BOLD, 32)
f_desc = ImageFont.truetype(REG, 23)
f_num = ImageFont.truetype(BOLD, 26)

def ease(x):
    x = max(0.0, min(1.0, x)); return 1 - (1 - x) ** 3

def background():
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(BG1[i] + (BG2[i] - BG1[i]) * k) for i in range(3)))
    for x in range(0, W, 48):
        d.line([(x, 0), (x, H)], fill=(18, 40, 70))
    for y in range(0, H, 48):
        d.line([(0, y), (W, y)], fill=(18, 40, 70))
    return img

BG = background()

def frame(t):
    img = BG.copy().convert("RGBA")
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    a = ease(t / 0.5)
    d.text((W / 2, 120), "AI MARKETING WORKFLOW", font=f_title, fill=WHITE + (int(255 * a),), anchor="mm")
    d.text((W / 2, 172), "Runs automatically from your CRM", font=f_sub, fill=MUTED + (int(255 * a),), anchor="mm")
    step_t = 0.5 + 0.7 * 0  # first box appears at 0.5s
    for i, (head, desc, col) in enumerate(STEPS):
        t0 = 0.5 + i * 0.75
        p = ease((t - t0) / 0.45)
        if p <= 0:
            continue
        y = TOP + i * (BOX_H + GAP) + int((1 - p) * 30)
        alpha = int(255 * p)
        # connector arrow from previous box, drawn progressively
        if i > 0:
            ya = TOP + i * (BOX_H + GAP) - GAP + 6
            yb = TOP + i * (BOX_H + GAP) - 8
            ly = ya + (yb - ya) * ease((t - t0 + 0.2) / 0.3)
            d.line([(W / 2, ya), (W / 2, ly)], fill=col + (alpha,), width=5)
            if ly >= yb - 1:
                d.polygon([(W / 2 - 11, yb - 12), (W / 2 + 11, yb - 12), (W / 2, yb + 2)], fill=col + (alpha,))
        d.rounded_rectangle([X0, y, X0 + BOX_W, y + BOX_H], radius=22, fill=(12, 30, 58, int(230 * p)),
                            outline=col + (alpha,), width=4)
        gd.rounded_rectangle([X0, y, X0 + BOX_W, y + BOX_H], radius=22, outline=col + (int(160 * p),), width=10)
        cx, cy = X0 + 62, y + BOX_H / 2
        d.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], fill=col + (alpha,))
        d.text((cx, cy), str(i + 1), font=f_num, fill=(8, 20, 40, alpha), anchor="mm")
        d.text((X0 + 114, y + 44), head, font=f_head, fill=WHITE + (alpha,), anchor="lm")
        d.text((X0 + 114, y + 90), desc, font=f_desc, fill=MUTED + (alpha,), anchor="lm")
    # travelling pulse once all boxes are in
    tp = t - (0.5 + 5 * 0.75 + 0.4)
    if tp > 0:
        yy = TOP + (tp % 1.6) / 1.6 * (5 * (BOX_H + GAP) + BOX_H)
        gd.ellipse([W / 2 - 16, yy - 16, W / 2 + 16, yy + 16], fill=GOLD + (220,))
    glow = glow.filter(ImageFilter.GaussianBlur(10))
    img = Image.alpha_composite(img, glow)
    img = Image.alpha_composite(img, layer)
    return img.convert("RGB")

def main():
    tmp = tempfile.mkdtemp()
    n = int(DUR * FPS)
    for k in range(n):
        frame(k / FPS).save(os.path.join(tmp, f"f{k:04d}.png"))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(tmp, "f%04d.png"),
                    "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", os.path.join(HERE, "workflow_diagram.mp4")], check=True)
    frame(DUR - 0.1).save(os.path.join(HERE, "workflow_diagram_still.png"))

if __name__ == "__main__":
    main()
