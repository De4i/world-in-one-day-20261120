# Build notes

- **Built:** Friday 20 November 2026 (Asia/Jakarta), for the make.fun
  bounty `news-image-20261120` — "Sum up 20 November's world news in one
  image".
- **Deliverable:** `entry.png`, a 1024×1024 PNG (≤ 1,048,576 bytes),
  copied to the output directory by `main.ts` (Node, standard library
  only). Two runs of `main.ts` produce byte-identical output.
- **Story count:** 38 stories — 3 illustrated leads, 10 feature modules,
  and 25 one-line briefs (numbered 14–38). Region counts printed on the
  poster (Europe 8 · Americas 7 · Asia-Pacific 10 · Mideast 3 · Africa 3 ·
  Oceania 5 · World/Space 2) sum to the same 38 and are asserted against
  the story list at build time.
- **Sources:** Reuters, AP, AFP, BBC, IMD, The Hindu, Kyiv Post, UN News,
  Al Jazeera, SBS, RNZ, UKMTO, CGIL, EU Council, PBOC, ESA, ICC, FIFA,
  BWF, ATP, Yonhap and RCB, as attributed per story on the poster. Claims
  are attributed, not stated as fact. A date-check box excludes stories
  first reported on Thursday 19 November.
- **Artwork:** all original and drawn in code with Pillow shapes — full
  lead illustration bands (the complete cyclone spiral over the coast
  with a Gopalpur landfall marker, the Kyiv night skyline with missile
  trails and fire glows over a river, the COP31 thermometer panel with
  deadlock arrows and a final-day banner), a drawn graphic band for each
  of the ten feature stories, and a halftone dot-grid world map built
  from hand-coded continent polygons with numbered pins 1–13.

## How to re-render

```sh
python3 poster/build_poster.py   # writes entry.png at the repo root
node main.ts                      # copies entry.png to the output dir
```

All poster content lives in `poster/data/stories.json`; all layout and
drawing lives in `poster/build_poster.py`. The render uses only the
system Liberation fonts and is fully deterministic (no randomness, no
network, no timestamps): re-running the build reproduces the same bytes.
If the plain PNG ever exceeds 1 MiB, the build script palette-quantises
it (224 colours, median-cut, Floyd–Steinberg dithering) so the output
always stays within the limit.
