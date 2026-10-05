#!/usr/bin/env python3
"""Assemble the 9:16 dealership AI ad from the generated clips + voiceover."""
import subprocess, os, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 768, 1344, 24
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
VO_LEN = 121.23
TAIL = 1.5

# (clip, source start, source length, output start, output end) — output times follow VO timestamps
SEGS = [
    ("clip01_exterior",      0.00, 6.59,   0.00,   6.92),
    ("clip02_showroom",      0.00, 6.59,   6.92,  13.84),
    ("clip03_crm_ai",        0.00, 8.00,  13.84,  22.40),  # "AI going into your CRM"
    ("clip04_phone_offer",   0.27, 6.32,  22.40,  28.72),  # "Marketing..."
    ("clip05_service",       0.00, 8.00,  28.72,  37.48),  # service
    ("clip06_winter_tires",  2.39, 4.20,  37.48,  41.68),  # winter tire sale
    ("clip07_parts",         0.00, 8.00,  41.68,  51.28),  # parts
    ("clip03_crm_ai",        5.12, 2.88,  51.28,  54.16),  # "...customers most likely to buy"
    ("clip08_sales_event",   0.00, 3.64,  54.16,  57.80),  # major sales event
    ("clip09_dashboard",     0.00, 4.82,  57.80,  62.62),  # AI working through database
    ("clip02_showroom",      1.77, 4.82,  62.62,  67.44),  # people coming back
    ("clip04_phone_offer",   3.00, 3.08,  67.44,  70.52),  # personalized offers / follow-up
    ("clip08_sales_event",   3.64, 6.50,  70.52,  77.24),  # sales + keys handover
    ("clip01_exterior",      0.00, 4.60,  77.24,  81.84),  # "across your dealership"
    ("clip02_showroom",      0.50, 0.88,  81.84,  82.72),  # sales
    ("clip05_service",       1.00, 0.76,  82.72,  83.48),  # service
    ("clip07_parts",         2.00, 0.88,  83.48,  84.36),  # parts
    ("clip09_dashboard",     3.00, 1.52,  84.36,  85.88),  # accounting
    ("clip03_crm_ai",        4.00, 4.00,  85.88,  89.92),  # find missed opportunities
    ("clip09_dashboard",     5.00, 5.14,  89.92,  95.08),  # new revenue
    ("clip10_drive_away",    0.00, 7.80,  95.08, 102.88),  # close
]
END_START = 102.88
END_LEN = VO_LEN + TAIL - END_START
SIGNUP_AT = 117.68 - END_START

def run(cmd):
    subprocess.run(cmd, check=True)

def esc(t):
    return t.replace("'", "’").replace(":", r"\:")

def text(t, size, y, start, end=None, color="white"):
    en = f"between(t,{start},{end})" if end else f"gte(t,{start})"
    fade = f"if(lt(t,{start}+0.4),(t-{start})/0.4,1)"
    return (f"drawtext=fontfile={FONT}:text='{esc(t)}':fontsize={size}:fontcolor={color}:"
            f"x=(w-text_w)/2:y={y}:enable='{en}':alpha='{fade}':shadowcolor=black@0.6:shadowx=3:shadowy=3")

def main():
    tmp = tempfile.mkdtemp()
    parts = []
    for i, (clip, ss, sl, o0, o1) in enumerate(SEGS):
        out_len = o1 - o0
        f = out_len / sl
        p = os.path.join(tmp, f"s{i:02d}.mp4")
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ss}", "-t", f"{sl}", "-i", os.path.join(HERE, clip + ".mp4"),
             "-vf", f"setpts={f}*(PTS-STARTPTS),fps={FPS},scale={W}:{H},setsar=1,tpad=stop_mode=clone:stop_duration=1",
             "-t", f"{out_len}", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", p])
        parts.append(p)

    # End card: slow, dimmed, blurred exterior shot with the call to action
    end = os.path.join(tmp, "end.mp4")
    f = END_LEN / 6.59
    vf = ",".join([
        f"setpts={f}*(PTS-STARTPTS),fps={FPS},scale={W}:{H},setsar=1,tpad=stop_mode=clone:stop_duration=5",
        "gblur=sigma=14", "eq=brightness=-0.18:saturation=0.9",
        f"drawbox=x=0:y=0:w=iw:h=ih:color=black@0.25:t=fill",
        text("DON'T TAKE OUR WORD FOR IT.", 34, "h*0.30", 0.3, SIGNUP_AT),
        text("3-DAY", 120, "h*0.38", 1.6, SIGNUP_AT, "#FFD54A"),
        text("FREE TRIAL", 96, "h*0.38+140", 1.9, SIGNUP_AT, "#FFD54A"),
        text("AI Receptionist", 40, "h*0.62", 5.5, SIGNUP_AT),
        text("+ AI Revenue Generation", 40, "h*0.62+56", 5.9, SIGNUP_AT),
        text("SIGN UP NOW.", 92, "h*0.40", SIGNUP_AT, None, "#FFD54A"),
        text("Turn your CRM", 54, "h*0.40+130", SIGNUP_AT + 1.0, None),
        text("into revenue.", 54, "h*0.40+196", SIGNUP_AT + 1.0, None),
        f"fade=t=out:st={END_LEN-0.6}:d=0.6",
    ])
    run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(HERE, "clip01_exterior.mp4"), "-vf", vf,
         "-t", f"{END_LEN}", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", end])
    parts.append(end)

    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as fh:
        fh.writelines(f"file '{p}'\n" for p in parts)
    silent = os.path.join(tmp, "video.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent])

    out = os.path.join(HERE, "dealership_ai_ad_9x16.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-i", silent, "-i", os.path.join(HERE, "voiceover.mp3"),
         "-filter_complex", f"[1:a]apad=pad_dur={TAIL},loudnorm=I=-16:TP=-1.5:LRA=11[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-shortest", "-movflags", "+faststart", out])
    print(out)

if __name__ == "__main__":
    main()
