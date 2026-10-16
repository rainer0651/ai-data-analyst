import subprocess, sys, numpy as np
src, out = sys.argv[1], sys.argv[2]
W, H, FPS, N = 618, 1080, 30, 2818
# (out_start, out_end, src_start, src_end, blend) in frames
P = [(0,270,0,270,0),
     (270,295.5,270,300,0),        # catch-up before "one of those names"
     (295.5,314,300,318.5,0),      # "those names" 0.15s earlier
     (314,323,318.5,323,1),        # ease back in the silence before the cut
     (323,513,323,513,0),
     (513,534,513,539,0),          # catch-up in pause after "dealership,"
     (534,584,539,589,0),          # "efficiently communicating with every" 0.17s earlier
     (584,613,589,613,1),          # ease back inside the SALES cutaway
     (613,N,613,N,0)]
def srcpos(n):
    for o0,o1,s0,s1,b in P:
        if o0 <= n < o1: return s0 + (n-o0)*(s1-s0)/(o1-o0), b
dec = subprocess.Popen(["ffmpeg","-v","error","-i",src,"-vf","scale=in_range=full:out_range=full,format=rgb24","-f","rawvideo","-"],stdout=subprocess.PIPE)
enc = subprocess.Popen(["ffmpeg","-y","-v","error","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}","-r",str(FPS),"-i","-","-i",src,
   "-map","0:v","-map","1:a","-vf","scale=out_range=limited:out_color_matrix=bt709,format=yuv420p",
   "-c:v","libx264","-profile:v","high","-level","4.0","-preset","slow","-crf","23","-g","60",
   "-colorspace","bt709","-color_primaries","bt709","-color_trc","bt709","-color_range","tv",
   "-c:a","aac","-b:a","160k","-ar","44100","-movflags","+faststart","-shortest",out],stdin=subprocess.PIPE)
buf = {}; nxt = 0; fs = W*H*3
def get(i):
    global nxt
    i = min(i, N-1)
    while nxt <= i:
        d = dec.stdout.read(fs)
        if len(d) < fs: break
        buf[nxt] = np.frombuffer(d, np.uint8).reshape(H,W,3); nxt += 1
    for k in [k for k in buf if k < i-2]: del buf[k]
    return buf[min(i, nxt-1)]
for n in range(N):
    s, b = srcpos(n)
    i = int(np.floor(s)); fr = s - i
    if b and fr > 1e-3:
        img = (get(i).astype(np.float32)*(1-fr) + get(i+1).astype(np.float32)*fr).round().astype(np.uint8)
    else:
        img = get(int(round(s)))
    enc.stdin.write(img.tobytes())
enc.stdin.close(); enc.wait(); dec.kill()
