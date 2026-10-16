#!/usr/bin/env python3
"""Build the 9:16 presenter video: retime each clip to its slice of the voiceover (picture only),
join, add cutaways, then lay the ORIGINAL continuous voiceover (vo2.wav) underneath — no audio seams."""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
FPS, W, H = 24, 768, 1344
VO = os.path.join(HERE, "vo2.wav")

def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                capture_output=True, text=True).stdout)

def build(raw, pieces, out, nframes):
    """pieces: (model_start, model_end, ours_start, ours_end) in seconds relative to the segment start."""
    fc = []
    for i, (m0, m1, o0, o1) in enumerate(pieces):
        f = (o1 - o0) / (m1 - m0)
        fc.append(f"[0:v]trim=start={m0}:end={m1},setpts=(PTS-STARTPTS)*{f:.5f}[v{i}]")
    fc.append("".join(f"[v{i}]" for i in range(len(pieces))) + f"concat=n={len(pieces)}:v=1:a=0[vc]")
    fc.append(f"[vc]fps={FPS},scale={W}:{H},setsar=1,tpad=stop_mode=clone:stop_duration=3[v]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-filter_complex", ";".join(fc), "-map", "[v]",
                    "-frames:v", str(nframes), "-an", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                    "-pix_fmt", "yuv420p", out], check=True)

def main():
    plan = json.load(open(os.path.join(HERE, "edit_plan.json")))
    gstart = json.load(open(os.path.join(HERE, "overlays.json")))["seg_gstart"]
    vo_len = dur(VO)
    tail = plan[-1].get("tail", 0.0)
    segs = []
    for k, c in enumerate(plan):
        s = gstart[c["name"]]
        e = gstart[plan[k + 1]["name"]] if k + 1 < len(plan) else vo_len + tail
        nframes = round(e * FPS) - round(s * FPS)          # frame-exact, so picture never drifts from the voiceover
        out = os.path.join(HERE, f"final_{c['name']}.mp4")
        build(os.path.join(HERE, c["raw"]), c["pieces"], out, nframes)
        segs.append(out)
    lst = os.path.join(HERE, "final_list.txt")
    open(lst, "w").writelines(f"file '{s}'\n" for s in segs)
    joined = os.path.join(HERE, "joined.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined], check=True)
    if os.path.exists(os.path.join(HERE, "overlays.json")):
        sys.path.insert(0, HERE); import apply_overlays
        apply_overlays.main("joined.mp4", "joined_ov.mp4")
        joined = os.path.join(HERE, "joined_ov.mp4")
    out = os.path.join(HERE, "presenter_ad_9x16.mp4")
    T = vo_len + tail
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", joined, "-i", VO,
                    "-filter_complex", f"[0:v]fade=t=out:st={T-0.5:.3f}:d=0.5[v];[1:a]apad=pad_dur={tail+0.5},loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]",
                    "-map", "[v]", "-map", "[a]", "-t", f"{T:.3f}", "-c:v", "libx264", "-crf", "20", "-preset", "medium",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out], check=True)
    print(out, round(dur(out), 2))

if __name__ == "__main__":
    main()
