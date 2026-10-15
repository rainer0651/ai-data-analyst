# Presenter video (9:16) — working files

- `presenter_ad_9x16_FULL.mp4` — current full-quality cut (1:34), with the 3 image cutaways.
- `presenter_ad_compatible.mp4` — smaller, maximum-compatibility copy.
- `clips/` — generated MiniMax H3 Max clips (raw, before retiming). `audio/` — Gemini "Iapetus" voiceover (`vo2.wav`) and its per-clip slices.
- `images/` — presenter stills/camera angles and the 3 cutaway images.
- `edit_plan.json` + `assemble.py` — the edit: per-clip retiming to the voiceover and the cutaways. To rebuild, copy
  `clips/*`, `audio/*` and `images/img*.jpg` into one folder with these two files and run `python3 assemble.py`.
