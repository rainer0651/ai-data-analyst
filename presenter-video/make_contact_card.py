#!/usr/bin/env python3
"""Contact card (768x1344) in texnet.ca colours. HOURS env var adds a business-hours line when known."""
import os
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 768, 1344
B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"; R = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
NAVY, TEAL, BG = (27, 0, 78), (0, 229, 185), (246, 248, 252)
hours = [h.strip() for h in os.environ.get("HOURS", "").split("|") if h.strip()]
im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
d.rectangle([0, 0, W, 14], fill=TEAL)
logo = Image.open(os.path.join(HERE, "anim", "texnet_logo.png")).convert("RGBA")
lw = 520; logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
im.paste(logo, ((W - lw) // 2, 150), logo)
y = 330
d.text((W / 2, y), "Got a question?", font=ImageFont.truetype(B, 54), fill=NAVY, anchor="mm"); y += 110
d.rounded_rectangle([60, y, W - 60, y + 200], radius=30, fill=(255, 255, 255), outline=(220, 225, 235), width=2)
d.text((W / 2, y + 62), "Call us", font=ImageFont.truetype(R, 34), fill=(90, 90, 120), anchor="mm")
d.text((W / 2, y + 135), "(604) 265-9369", font=ImageFont.truetype(B, 62), fill=NAVY, anchor="mm"); y += 240
if hours:
    hh = 90 + 56 * len(hours)
    d.rounded_rectangle([60, y, W - 60, y + hh], radius=30, fill=(255, 255, 255), outline=(220, 225, 235), width=2)
    d.text((W / 2, y + 52), "Business Hours", font=ImageFont.truetype(B, 36), fill=NAVY, anchor="mm")
    for i, line in enumerate(hours):
        d.text((W / 2, y + 112 + i * 56), line, font=ImageFont.truetype(R, 32), fill=(60, 60, 90), anchor="mm")
    y += hh + 40
d.rounded_rectangle([60, y, W - 60, y + 160], radius=30, fill=NAVY)
d.text((W / 2, y + 55), "or use our contact form", font=ImageFont.truetype(R, 32), fill=(220, 225, 245), anchor="mm")
d.text((W / 2, y + 112), "texnet.ca", font=ImageFont.truetype(B, 48), fill=TEAL, anchor="mm")
im.save(os.path.join(HERE, "anim", "contact_card.jpg"), quality=95)
im.resize((W // 3, H // 3)).save(os.path.join(HERE, "anim", "contact_preview.png"))
