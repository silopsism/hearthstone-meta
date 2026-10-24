# Hearthstone meta

Black Empire card analysis from HSGuru deck stats, published at https://hs.salwood.co.za.

- `data/` — deck lists and archetype stats transcribed from HSGuru screenshots
- `analyze_decks.py` — core / flex / experimental breakdown per archetype: `python analyze_decks.py data/decks_top5k_2026-10-24.csv`
- `tools/infographic/` — page template and build script; `python tools/infographic/build_data.py` rebuilds `site/black-empire-census/index.html`
- `site/` — static site served by nginx (`Dockerfile`, `nginx.conf`), deployed on Coolify

Card art: HearthstoneJSON tiles.
