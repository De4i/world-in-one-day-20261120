# World in One Day — Friday 20 November 2026

[![news-image-20261120](https://make.fun/badge/news-image-20261120.svg)](https://make.fun/bounty/news-image-20261120)
[![rank](https://make.fun/badge/news-image-20261120/De4i/world-in-one-day-20261120/rank.svg)](https://make.fun/bounty/news-image-20261120)
[![reward](https://make.fun/badge/news-image-20261120/De4i/world-in-one-day-20261120/reward.svg)](https://make.fun/bounty/news-image-20261120)

One page, one image, one day of world news. This entry sums up Friday
20 November 2026 as a single 1024×1024 newspaper poster: a masthead with
the date, a strip of the day's biggest numbers, three illustrated lead
stories (Cyclone Akvan's landfall in India, the missile wave on Kyiv, and
COP31's deadlocked final day), ten feature modules with original drawn
icons, a dotted world map with numbered pins, and 25 further stories in
brief — 38 stories across 6 continents, every claim attributed to its
source, plus a date-check box listing the big stories that were actually
first reported on Thursday 19 November and so do not belong here.

Competition: [make.fun — news-image-20261120](https://make.fun/bounty/news-image-20261120)

## Run

```sh
node main.ts
```

`main.ts` (Node, standard library only) copies the baked `entry.png`
beside it to `$MAKEFUN_OUTPUT_DIR/entry.png`, or to `/output/entry.png`
when the variable is not set, creating the output directory if needed.
The output is byte-identical on every run.

## Rebuild the poster

```sh
python3 poster/build_poster.py
```

That re-renders `entry.png` from `poster/data/stories.json` with Pillow.
See [BUILD.md](BUILD.md) for build notes.

## License

MIT — see [LICENSE](LICENSE).
