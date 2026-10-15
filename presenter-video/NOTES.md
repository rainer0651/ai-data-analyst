# Presenter video (9:16) — working files

- `presenter_ad_9x16_FULL.mp4` — current full-quality cut (1:34), with the 3 image cutaways.
- `presenter_ad_compatible.mp4` — smaller, maximum-compatibility copy.
- `clips/` — generated MiniMax H3 Max clips (raw, before retiming). `audio/` — Gemini "Iapetus" voiceover (`vo2.wav`) and its per-clip slices.
- `images/` — presenter stills/camera angles and the 3 cutaway images.
- `edit_plan.json` + `assemble.py` — the edit: per-clip retiming to the voiceover and the cutaways. To rebuild, copy
  `clips/*`, `audio/*` and `images/img*.jpg` into one folder with these two files and run `python3 assemble.py`.

## Update: cutaways (v3)
- `overlays.json` + `apply_overlays.py` — cutaways timed to words (from `words.json` transcript): 4 departments
  (reuses ../dealership-ad-2 clips c08/c04/c06b/c11 — copy them into `anim/` before rebuilding), CRM screen sequence
  (`anim/crm_anim.mp4`, rendered by `make_crm_anim.py`), Advertising/Marketing customer reactions, salesman + lead card,
  AI receptionist still (frame from texnet.ca receptionist video).
