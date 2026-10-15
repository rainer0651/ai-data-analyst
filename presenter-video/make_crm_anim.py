#!/usr/bin/env python3
"""Render the CRM screen animation (8.7 s, 768x1344): list scroll -> AI picks names -> text offer -> click Send."""
import os, subprocess, tempfile, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS, DUR = 768, 1344, 24, 8.7
B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"; R = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
F = lambda p, s: ImageFont.truetype(p, s)
NAVY, PANEL, ROW, ROW2, LINE = (11, 22, 44), (18, 33, 61), (24, 42, 76), (28, 48, 84), (40, 62, 100)
WHITE, MUTED, TEAL, GOLD, GREEN = (240, 245, 252), (150, 170, 196), (45, 212, 191), (255, 205, 60), (60, 200, 110)
ROWS = [("Daniel Brooks", "Service · 2019 Civic", "Oil change 3 wks ago"), ("Priya Shah", "Lead · Spring 2026", "Asked about hybrids"),
        ("Sarah Mitchell", "Lease ends Dec 2026", "Wants bigger SUV"), ("Tom Alvarez", "Parts · Wipers", "Bought 2017 F-150"),
        ("Linda Chen", "Service · 2020 RAV4", "Brake inspection"), ("Marcus Reid", "Lead · Went cold", "Test drove Tacoma"),
        ("Emily Nguyen", "Bought 2021 Corolla", "Growing family"), ("James O'Connor", "Service · 2018 Equinox", "High mileage"),
        ("Aisha Khan", "Lead · Website", "Trade-in question"), ("Robert Fox", "Lease ends Jan 2027", "Loves the brand"),
        ("Nina Petrova", "Service · 2016 Jetta", "Repair estimate high"), ("Greg Walsh", "Parts · Tires", "Winter tire quote"),
        ("Maria Lopez", "Bought 2019 Tucson", "5 yr owner"), ("Kevin Park", "Lead · Phone call", "Price shopping"),
        ("Olivia Grant", "Service · 2021 Mazda3", "Recall done"), ("Chris Baker", "Lead · Spring 2026", "Pre-approved")]
PICK = {2: "94%", 5: "89%", 9: "91%"}           # rows that get picked, with likelihood
TOP, RH = 210, 92
def ease(x): x = max(0., min(1., x)); return 1 - (1 - x) ** 3
def pop(x): x = max(0., min(1., x)); return 1 + 0.25 * math.sin(math.pi * x) * (1 - x)

def frame(t):
    im = Image.new("RGB", (W, H), NAVY); d = ImageDraw.Draw(im)
    # app header
    d.rectangle([0, 0, W, 150], fill=PANEL)
    d.text((40, 42), "Dealer CRM", font=F(B, 40), fill=WHITE)
    d.text((40, 98), "Customer Database  ·  12,847 records", font=F(R, 24), fill=MUTED)
    d.rounded_rectangle([W - 210, 52, W - 36, 104], radius=26, fill=TEAL)
    d.text((W - 123, 78), "AI scan", font=F(B, 24), fill=NAVY, anchor="mm")
    # scrolling list
    scroll = 330 * ease(t / 2.8) + 40 * max(0, t - 2.8)
    scroll = min(scroll, 360)
    list_layer = Image.new("RGB", (W, H - TOP), NAVY); ld = ImageDraw.Draw(list_layer)
    pick_t = {2: 3.5, 5: 4.0, 9: 4.5}
    for i, (nm, a, b) in enumerate(ROWS):
        y = i * RH - scroll
        if y < -RH or y > H: continue
        hi = i in PICK and t >= pick_t[i]
        fill = (70, 58, 20) if hi else (ROW if i % 2 else ROW2)
        ld.rounded_rectangle([24, y + 6, W - 24, y + RH - 6], radius=14, fill=fill, outline=GOLD if hi else LINE, width=3 if hi else 1)
        ld.ellipse([44, y + 22, 92, y + 70], fill=GOLD if hi else LINE)
        ld.text((68, y + 46), nm[0], font=F(B, 24), fill=NAVY if hi else WHITE, anchor="mm")
        ld.text((112, y + 20), nm, font=F(B, 26), fill=WHITE)
        ld.text((112, y + 56), f"{a}  ·  {b}", font=F(R, 19), fill=MUTED)
    im.paste(list_layer, (0, TOP))
    # AI scan sweep
    if 1.0 < t < 5.0:
        sy = TOP + ((t - 1.0) / 1.2 % 1) * (H - TOP)
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); g = ImageDraw.Draw(glow)
        g.rectangle([0, sy - 3, W, sy + 3], fill=TEAL + (230,)); glow = glow.filter(ImageFilter.GaussianBlur(6))
        im.paste(glow, (0, 0), glow); d.rectangle([0, sy - 1, W, sy + 1], fill=TEAL)
    # picked name cards pop out to the top
    for k, (i, pct) in enumerate(sorted(PICK.items())):
        t0 = pick_t[i] + 0.25
        if t < t0 or t > 5.9: continue
        p = ease((t - t0) / 0.45); s = pop((t - t0) / 0.45)
        cw, ch = 560 * s, 96 * s
        cx, cy = W / 2, 330 + k * 118
        card = Image.new("RGBA", (W, H), (0, 0, 0, 0)); c = ImageDraw.Draw(card)
        c.rounded_rectangle([cx - cw / 2 + 6, cy - ch / 2 + 10, cx + cw / 2 + 6, cy + ch / 2 + 10], radius=18, fill=(0, 0, 0, int(110 * p)))
        c.rounded_rectangle([cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2], radius=18, fill=(255, 255, 255, int(255 * p)), outline=GOLD + (int(255 * p),), width=4)
        if s > 0.9:
            c.text((cx - cw / 2 + 26, cy - 18), ROWS[i][0], font=F(B, 30), fill=(20, 30, 50, int(255 * p)), anchor="lm")
            c.text((cx - cw / 2 + 26, cy + 20), "Most likely to buy now", font=F(R, 20), fill=(90, 100, 120, int(255 * p)), anchor="lm")
            c.rounded_rectangle([cx + cw / 2 - 130, cy - 24, cx + cw / 2 - 20, cy + 24], radius=24, fill=GREEN + (int(255 * p),))
            c.text((cx + cw / 2 - 75, cy), pct, font=F(B, 24), fill=(255, 255, 255, int(255 * p)), anchor="mm")
        im.paste(card, (0, 0), card)
    # text offer composer
    if t >= 5.8:
        p = ease((t - 5.8) / 0.4)
        y0 = H - 760 * p
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
        sd.rectangle([0, 0, W, H], fill=(0, 0, 0, int(120 * p)))
        im.paste(sh, (0, 0), sh); d = ImageDraw.Draw(im)
        d.rounded_rectangle([20, y0, W - 20, y0 + 760], radius=34, fill=(245, 247, 251))
        d.text((56, y0 + 40), "New Text Offer", font=F(B, 32), fill=(20, 30, 50))
        d.text((56, y0 + 92), "To: Sarah Mitchell  ·  (604) ***-**21", font=F(R, 22), fill=(90, 100, 120))
        msg = ("Hi Sarah! Your lease is up soon. Upgrade to a new SUV with $0 down and get FREE winter tires. "
               "Want to book a test drive this week? Reply YES")
        n = int(len(msg) * max(0, min(1, (t - 6.1) / 1.3)))
        bub = Image.new("RGBA", (W, H), (0, 0, 0, 0)); bd = ImageDraw.Draw(bub)
        bs = pop((t - 6.1) / 0.35) if t > 6.1 else 0
        words, lines, cur = msg[:n].split(" "), [], ""
        for w in words:
            if bd.textlength((cur + " " + w).strip(), font=F(R, 28)) > 560: lines.append(cur); cur = w
            else: cur = (cur + " " + w).strip()
        lines.append(cur)
        bx0, by0 = 56, y0 + 160
        bh = 40 + 42 * max(1, len(lines))
        if bs > 0:
            bd.rounded_rectangle([bx0, by0, bx0 + 600 * bs, by0 + bh * bs], radius=26, fill=(33, 132, 255))
            if bs > 0.95:
                for li, ln in enumerate(lines):
                    bd.text((bx0 + 22, by0 + 22 + li * 42), ln, font=F(R, 28), fill=(255, 255, 255))
        im.paste(bub, (0, 0), bub); d = ImageDraw.Draw(im)
        # send button + cursor click
        bx, by = W - 260, y0 + 620
        pressed = 7.85 <= t < 8.05
        sent = t >= 8.05
        col = GREEN if sent else ((20, 100, 220) if pressed else (33, 132, 255))
        d.rounded_rectangle([bx, by + (4 if pressed else 0), bx + 200, by + 76], radius=38, fill=col)
        d.text((bx + 100, by + 38), "Sent ✓" if sent else "Send", font=F(B, 32), fill=(255, 255, 255), anchor="mm")
        if t >= 7.3:
            q = ease((t - 7.3) / 0.5)
            mx, my = 250 + (bx + 120 - 250) * q, y0 + 760 + (by + 50 - (y0 + 760)) * q
            pts = [(mx, my), (mx, my + 44), (mx + 12, my + 33), (mx + 21, my + 52), (mx + 29, my + 48), (mx + 20, my + 30), (mx + 36, my + 30)]
            d.polygon(pts, fill=(255, 255, 255), outline=(0, 0, 0))
            if pressed:
                d.ellipse([mx - 24, my - 24, mx + 24, my + 24], outline=(33, 132, 255), width=4)
        if sent:
            a = ease((t - 8.05) / 0.25)
            d.rounded_rectangle([W / 2 - 220, 170, W / 2 + 220, 250], radius=40, fill=GREEN)
            d.text((W / 2, 210), "Offer sent to 3 customers", font=F(B, 26), fill=(255, 255, 255), anchor="mm")
    return im

def main():
    tmp = tempfile.mkdtemp()
    for k in range(int(DUR * FPS)):
        frame(k / FPS).save(os.path.join(tmp, f"f{k:04d}.png"))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(tmp, "f%04d.png"),
                    "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", os.path.join(HERE, "anim", "crm_anim.mp4")], check=True)
    for t in (1.5, 4.9, 7.0, 8.4):
        frame(t).resize((W // 3, H // 3)).save(os.path.join(HERE, "anim", f"crm_{t}.png"))
if __name__ == "__main__":
    main()
