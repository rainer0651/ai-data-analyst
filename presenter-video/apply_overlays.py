#!/usr/bin/env python3
"""Composite global (voiceover-timed) cutaways onto joined.mp4 -> joined_ov.mp4."""
import json, os, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
FPS, W, H = 24, 768, 1344
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
def dur(p):
    return float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p],capture_output=True,text=True).stdout)
def main(src="joined.mp4", out="joined_ov.mp4"):
    cfg = json.load(open(os.path.join(HERE, "overlays.json")))
    plan = json.load(open(os.path.join(HERE, "edit_plan.json")))
    js, acc = [], 0.0
    for c in plan:
        js.append((cfg["seg_gstart"][c["name"]], acc)); acc += dur(os.path.join(HERE, f"final_{c['name']}.mp4"))
    def m(t):
        g, j = [x for x in js if x[0] <= t + 1e-6][-1]
        return j + (t - g)
    ins, fc, last = ["-i", os.path.join(HERE, src)], [], "0:v"
    for k, o in enumerate(cfg["overlays"]):
        t0, t1 = m(o["start"]), m(o["end"]); d = t1 - t0; idx = k + 1; p = os.path.join(HERE, o["src"])
        if o["kind"] == "image":
            ins += ["-loop", "1", "-framerate", str(FPS), "-t", f"{d + 0.2:.3f}", "-i", p]
            n = int(d * FPS) + 2
            chain = (f"[{idx}:v]scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
                     f"zoompan=z='1+0.06*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},setsar=1,format=yuv420p")
        elif o["kind"] == "alpha":
            ins += ["-i", p]
            chain = f"[{idx}:v]trim=duration={d:.3f},setpts=(PTS-STARTPTS)*{d/dur(p):.5f},fps={FPS},format=yuva420p"
        else:
            s0 = o.get("src_start", 0.0); s1 = o.get("src_end", s0 + d)
            ins += ["-ss", f"{s0}", "-t", f"{s1 - s0:.3f}", "-i", p]
            f = d / (s1 - s0)
            chain = (f"[{idx}:v]setpts=(PTS-STARTPTS)*{f:.5f},fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,"
                     f"crop={W}:{H},setsar=1,format=yuv420p,tpad=stop_mode=clone:stop_duration=1")
            if o.get("label"):
                chain += (f",drawtext=fontfile={FONT}:text='{o['label']}':fontsize=64:fontcolor=#FFD54A:x=(w-text_w)/2:y=h*0.80:"
                          f"box=1:boxcolor=black@0.45:boxborderw=18:shadowcolor=black@0.6:shadowx=3:shadowy=3")
        fc.append(chain + f",setpts=PTS-STARTPTS+{t0:.3f}/TB[o{k}]")
        fc.append(f"[{last}][o{k}]overlay=enable='between(t,{t0:.3f},{t1:.3f})':eof_action=pass[v{k}]")
        last = f"v{k}"
    subprocess.run(["ffmpeg","-v","error","-y",*ins,"-filter_complex",";".join(fc),"-map",f"[{last}]","-map","0:a",
                    "-c:v","libx264","-crf","18","-preset","medium","-pix_fmt","yuv420p","-c:a","copy",os.path.join(HERE,out)],check=True)
    print("ok", round(dur(os.path.join(HERE, out)), 2))
if __name__ == "__main__":
    main()
