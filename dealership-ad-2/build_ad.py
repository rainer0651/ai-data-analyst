#!/usr/bin/env python3
"""Assemble ad #2 (9:16, female VO) from generated clips, the rendered workflow diagram and voiceover."""
import subprocess, os, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 768, 1344, 24
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
VO_LEN, TAIL = 61.65, 2.0
GOLD = "#FFD54A"
# Exterior shot has a small red sign top-right: crop it out (keep bottom-left 86%)
# Exterior shot has a small red sign that drifts up the facade: cover it with a moving blur patch
SIGN_BLUR = ("split[m][s];[s]crop=110:110:575:'1344*(0.43-0.0198*t)-55',boxblur=20:3[b];"
             "[m][b]overlay=575:'1344*(0.43-0.0198*t)-55'")
PRE = {"c01_exterior": SIGN_BLUR}

# (clip, src start, src len, out start, out end, label or None)
SEGS = [
    ("c01_exterior",        0.00, 5.06,  0.00,  5.06, None),
    ("c02_showroom",        0.00, 6.86,  5.06, 11.92, None),
    ("c03_database",        2.10, 3.08, 11.92, 15.00, None),   # "AI going into your database"
    ("workflow_diagram",    0.00, 6.00, 15.00, 21.00, None),   # "creating marketing workflows"
    ("c04_service",         0.30, 3.00, 21.00, 24.00, None),   # free tire rotation + brake inspection
    ("c05_winter_tire",     1.00, 1.96, 24.00, 25.96, None),   # winter tire sale
    ("c06_parts",           0.84, 3.64, 25.96, 29.60, None),   # washer fluid
    ("c07_event_aerial",    0.00, 6.59, 29.60, 36.24, None),   # sales event
    ("c08_event_keys",      1.15, 5.44, 36.24, 41.68, None),   # once-in-a-lifetime
    ("c09_dashboard",       1.70, 3.48, 41.68, 45.16, None),   # power of the AI tool
    ("c10_ai_receptionist", 0.45, 6.84, 45.16, 52.00, None),   # free trial / AI receptionist
    ("workflow_diagram",    2.64, 3.36, 52.00, 55.36, None),   # revenue through your CRM
    ("c04_service",         3.20, 1.24, 55.36, 56.60, "SERVICE"),
    ("c08_event_keys",      0.20, 0.70, 56.60, 57.30, "SALES"),
    ("c06_parts",           0.00, 0.80, 57.30, 58.10, "PARTS"),
    ("c11_accounting",      1.20, 2.58, 58.10, 60.68, "ACCOUNTING"),
]
END_START = 60.68
END_LEN = VO_LEN + TAIL - END_START

def run(cmd):
    subprocess.run(cmd, check=True)

def esc(t):
    return t.replace("'", "’").replace(":", r"\:")

def text(t, size, y, start=0.0, end=None, color="white", box=False):
    en = f":enable='between(t,{start},{end})'" if end is not None else ""
    b = ":box=1:boxcolor=black@0.45:boxborderw=18" if box else ""
    return (f"drawtext=fontfile={FONT}:text='{esc(t)}':fontsize={size}:fontcolor={color}:x=(w-text_w)/2:y={y}"
            f"{en}:alpha='min(1,(t-{start})/0.3)':shadowcolor=black@0.6:shadowx=3:shadowy=3{b}")

def main():
    tmp = tempfile.mkdtemp()
    parts = []
    for i, (clip, ss, sl, o0, o1, label) in enumerate(SEGS):
        out_len = o1 - o0
        f = out_len / sl
        vf = ([PRE[clip]] if clip in PRE else []) + [f"setpts={f}*(PTS-STARTPTS)", f"fps={FPS}", f"scale={W}:{H}", "setsar=1",
              "tpad=stop_mode=clone:stop_duration=1"]
        if label:
            vf.append(text(label, 64, "h*0.80", 0.0, None, GOLD, box=True))
        if i == 10:  # AI receptionist shot carries the trial callout
            vf += [text("3-DAY FREE TRIAL", 62, "h*0.10", 0.2, None, GOLD, box=True),
                   text("AI RECEPTIONIST", 44, "h*0.80", 2.4, None, "white", box=True)]
        p = os.path.join(tmp, f"s{i:02d}.mp4")
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ss}", "-t", f"{sl}", "-i", os.path.join(HERE, clip + ".mp4"),
             "-vf", ",".join(vf), "-t", f"{out_len}", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-pix_fmt", "yuv420p", p])
        parts.append(p)

    end = os.path.join(tmp, "end.mp4")
    vf = ",".join([
        SIGN_BLUR, f"setpts=2*(PTS-STARTPTS),fps={FPS}", f"scale={W}:{H}", "setsar=1", "tpad=stop_mode=clone:stop_duration=5",
        "gblur=sigma=14", "eq=brightness=-0.2", "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.25:t=fill",
        text("SIGN UP NOW.", 78, "h*0.36", 0.0, None, GOLD),
        text("3-DAY FREE TRIAL", 58, "h*0.36+140", 0.5),
        text("AI Receptionist + AI Revenue Tools", 32, "h*0.36+225", 0.9),
        f"fade=t=out:st={END_LEN-0.6}:d=0.6",
    ])
    run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(HERE, "c01_exterior.mp4"), "-vf", vf, "-t", f"{END_LEN}",
         "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", end])
    parts.append(end)

    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as fh:
        fh.writelines(f"file '{p}'\n" for p in parts)
    silent = os.path.join(tmp, "video.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent])
    out = os.path.join(HERE, "dealership_ai_ad2_9x16.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-i", silent, "-i", os.path.join(HERE, "voiceover.mp3"),
         "-filter_complex", f"[1:a]apad=pad_dur={TAIL},loudnorm=I=-16:TP=-1.5:LRA=11[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-shortest", "-movflags", "+faststart", out])
    print(out)

if __name__ == "__main__":
    main()
