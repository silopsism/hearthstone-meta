import csv, json, os, sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, PROJ)
from analyze_decks import CLASS_OF  # noqa: E402

cards = json.load(open(os.path.join(HERE, "cards.json"), encoding="utf-8"))
be_all = json.load(open(os.path.join(HERE, "be_epic_leg.json"), encoding="utf-8"))

LEVELS = {"d4": "data/decks_diamond_2026-10-24.csv", "t5k": "data/decks_top5k_2026-10-24.csv"}


def load(path):
    out = []
    for r in csv.DictReader(open(os.path.join(PROJ, path), encoding="utf-8")):
        wr, g = float(r["winrate"]), int(r["games"])
        out.append({"arch": r["archetype"], "wr": wr, "games": g, "w": g * max(wr - 50, 0),
                    "cards": [c for c in r["be_epic_legendary"].split(";") if c]})
    return out


data = {"levels": {}, "cards": json.load(open(os.path.join(HERE, "all_cards.json"), encoding="utf-8"))}
for key, path in LEVELS.items():
    decks = load(path)
    archs = defaultdict(list)
    for d in decks:
        archs[d["arch"]].append(d)
    lvl = {"lists": len(decks), "games": sum(d["games"] for d in decks), "archetypes": {}, "cardLists": defaultdict(int)}
    for d in decks:
        for c in d["cards"]:
            lvl["cardLists"][c] += 1
    for a, ds in archs.items():
        games = sum(d["games"] for d in ds)
        wsum = sum(d["w"] for d in ds) or 1
        entry = {"cls": CLASS_OF.get(a, "?"), "lists": len(ds), "games": games,
                 "wr": round(sum(d["wr"] * d["games"] for d in ds) / games, 1),
                 "best": max(d["wr"] for d in ds), "cards": {}}
        for c in {c for d in ds for c in d["cards"]}:
            inc = [d for d in ds if c in d["cards"]]
            exc = [d for d in ds if c not in d["cards"]]
            wr_in = sum(d["wr"] * d["games"] for d in inc) / sum(d["games"] for d in inc)
            wr_out = sum(d["wr"] * d["games"] for d in exc) / sum(d["games"] for d in exc) if exc else None
            entry["cards"][c] = {"n": len(inc), "share": round(sum(d["w"] for d in inc) / wsum, 2),
                                 "delta": round(wr_in - wr_out, 1) if wr_out is not None else None}
        lvl["archetypes"][a] = entry
    data["levels"][key] = lvl

played = set(cards)
data["unplayed"] = sorted(([c["cls"], c["rarity"], c["name"]] for c in be_all if c["name"] not in played))
data["meta"] = [r for r in csv.DictReader(open(os.path.join(PROJ, "data/archetypes_2026-10-24.csv"), encoding="utf-8"))]
blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
page = tpl.replace("/*__DATA__*/null", blob)
# artifact version: the artifact viewer supplies the document skeleton
open(os.path.join(HERE, "black-empire-census.html"), "w", encoding="utf-8").write(page)
# standalone version for the web server
head, _, rest = page.partition('<div class="wrap">')
standalone = ('<!doctype html>\n<html lang="en">\n<head>\n'
              '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
              + head + '<style>body{margin:0}</style>\n</head>\n<body>\n<div class="wrap">' + rest + "\n</body>\n</html>\n")
out = os.path.join(PROJ, "site", "black-empire-census", "index.html")
open(out, "w", encoding="utf-8").write(standalone)
print({k: (v["lists"], v["games"]) for k, v in data["levels"].items()}, len(data["unplayed"]), "unplayed")
for k in ("d4", "t5k"):
    print(k, sorted(data["levels"][k]["cardLists"].items(), key=lambda t: -t[1])[:6])
