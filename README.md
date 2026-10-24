# Hearthstone meta

Black Empire card analysis from HSGuru deck stats, published at https://hs.salwood.co.za.

- `data/lists_2026-10-24.csv` — every list's full card names, transcribed from HSGuru screenshots (Diamond 4-1 and Top 5k)
- `data/decks_*.csv`, `data/archetypes_*.csv` — per-level Black Empire tags and archetype stats
- `analyze_decks.py` — core / flex / experimental breakdown per archetype: `python analyze_decks.py data/decks_top5k_2026-10-24.csv`
- `tools/infographic/` — page template and `build_census.py`, which treats each archetype as one deck, scores Black Empire epics and legendaries for crafting and rebuilds `site/black-empire-census/index.html`. It needs HearthstoneJSON's full card file: `python tools/infographic/build_census.py path/to/cards.json` (from https://api.hearthstonejson.com/v1/latest/enUS/cards.json)
- `site/` — static site served by nginx (`Dockerfile`, `nginx.conf`), deployed on Coolify

Card art: HearthstoneJSON tiles.
