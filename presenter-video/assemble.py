#!/usr/bin/env python3
"""Retime each generated clip to its slice of the voiceover and join into the final 9:16 video."""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
FPS, W, H = 24, 768, 1344

def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                capture_output=True, text=True).stdout)

def build(raw, audio, pieces, out, tail=0.0, overlays=()):
    """pieces: list of (model_start, model_end, ours_start, ours_end); maps model-time spans onto voiceover time."""
    alen = dur(audio)
    total = alen + tail
    fc = []
    for i, (m0, m1, o0, o1) in enumerate(pieces):
        f = (o1 - o0) / (m1 - m0)
        fc.append(f"[0:v]trim=start={m0}:end={m1},setpts=(PTS-STARTPTS)*{f:.5f}[v{i}]")
    fc.append("".join(f"[v{i}]" for i in range(len(pieces))) + f"concat=n={len(pieces)}:v=1:a=0[vc]")
    fc.append(f"[vc]fps={FPS},scale={W}:{H},setsar=1,tpad=stop_mode=clone:stop_duration=3[v0]")
    extra = []
    last = "v0"
    for k, ov in enumerate(overlays):  # full-frame image cutaways with a slow push-in
        t0, t1 = ov["start"], ov["end"]
        n = int(round((t1 - t0) * FPS)) + 2
        idx = 2 + k
        extra += ["-loop", "1", "-framerate", str(FPS), "-t", f"{t1 - t0 + 0.2:.3f}", "-i", os.path.join(HERE, ov["image"])]
        fc.append(f"[{idx}:v]scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
                  f"zoompan=z='1+0.06*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},"
                  f"setsar=1,format=yuv420p,setpts=PTS-STARTPTS+{t0}/TB[o{k}]")
        fc.append(f"[{last}][o{k}]overlay=enable='between(t,{t0},{t1})':eof_action=pass[v{k+1}]")
        last = f"v{k+1}"
    fc.append(f"[{last}]null[v]")
    fc.append(f"[1:a]apad=pad_dur={tail + 0.5},aresample=48000[a]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-i", audio, *extra, "-filter_complex", ";".join(fc),
                    "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", out], check=True)

def main():
    plan = json.load(open(os.path.join(HERE, "edit_plan.json")))
    segs = []
    for c in plan:
        out = os.path.join(HERE, f"final_{c['name']}.mp4")
        build(os.path.join(HERE, c["raw"]), os.path.join(HERE, c["audio"]), c["pieces"], out, c.get("tail", 0.0),
              c.get("overlays", ()))
        segs.append(out)
    lst = os.path.join(HERE, "final_list.txt")
    open(lst, "w").writelines(f"file '{s}'\n" for s in segs)
    joined = os.path.join(HERE, "joined.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined], check=True)
    out = os.path.join(HERE, "presenter_ad_9x16.mp4")
    T = dur(joined)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", joined, "-vf", f"fade=t=out:st={T-0.5:.3f}:d=0.5",
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:v", "libx264", "-crf", "20", "-preset", "medium",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", out], check=True)
    print(out, round(dur(out), 2))

if __name__ == "__main__":
    main()
