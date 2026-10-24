"""Build the craft-guide data from full deck lists, then render the page.

Each archetype is treated as one deck: its lists are variants, and a card's
share is the weighted fraction of those variants that run it.
Weight per list = games * (winrate - 50).

Usage: python tools/infographic/build_census.py <path to HearthstoneJSON cards_all.json>
"""
import base64, csv, json, os, statistics, sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, PROJ)
from analyze_decks import CLASS_OF  # noqa: E402

CORE, FLEX = 0.8, 0.3
DUST = {"LEGENDARY": 1600, "EPIC": 400, "RARE": 100, "COMMON": 40}
FREE_SETS = {"CORE", "EVENT", "LEGACY", "VANILLA"}
SET_NAMES = {"BE": "Black Empire", "TIME_TRAVEL": "Across the Timeways", "CATACLYSM": "Cataclysm",
             "EMERALD_DREAM": "Into the Emerald Dream", "ESCAPEFROM_VIOLET_HOLD": "Escape from Violet Hold",
             "SPACE": "The Great Dark Beyond", "ISLAND_VACATION": "Perils in Paradise",
             "WHIZBANGS_WORKSHOP": "Whizbang's Workshop", "THE_LOST_CITY": "The Lost City of Un'Goro",
             "CORE": "Core (free)", "EVENT": "Event"}
TRAP = {"N'Zoth, Dream's End": "Defines N'Zoth Handbuff DK, but plain BFU Handbuff DK without it wins more at both levels."}

allc = json.load(open(sys.argv[1], encoding="utf-8"))
by_name = {}
for c in allc:
    if c.get("set") == "HERO_SKINS":
        continue
    prev = by_name.get(c["name"])
    if prev is None or (c.get("collectible") and not prev.get("collectible")):
        by_name[c["name"]] = c

lists = []
for r in csv.DictReader(open(os.path.join(PROJ, "data", "lists_2026-10-24.csv"), encoding="utf-8")):
    wr, g = float(r["winrate"]), int(r["games"])
    lists.append({"id": r["deck"], "level": r["level"], "arch": r["archetype"], "wr": wr, "games": g,
                  "dust": int(r["dust"]), "w": g * max(wr - 50, 0), "cards": [x for x in r["cards"].split(";") if x]})

cards = {}
for L in lists:
    for n in L["cards"]:
        c = by_name[n]
        cards[n] = {"id": c["id"], "rarity": c.get("rarity") or "FREE", "set": c.get("set"),
                    "setName": SET_NAMES.get(c.get("set"), (c.get("set") or "").replace("_", " ").title()),
                    "cls": c.get("cardClass"), "cost": c.get("cost"), "collectible": bool(c.get("collectible"))}


def craftable(n):
    c = cards[n]
    return c["collectible"] and c["rarity"] in ("EPIC", "LEGENDARY") and c["set"] not in FREE_SETS


def dust_of(n):
    r = cards[n]["rarity"]
    return DUST[r] * (1 if r == "LEGENDARY" else 2)


archs = defaultdict(list)
for L in lists:
    archs[L["arch"]].append(L)

arch_out = {}
for a, ls in archs.items():
    ls.sort(key=lambda x: -x["wr"])
    W = sum(x["w"] for x in ls) or 1
    games = sum(x["games"] for x in ls)
    share = {}
    for n in {n for x in ls for n in x["cards"]}:
        inc = [x for x in ls if n in x["cards"]]
        share[n] = {"share": round(sum(x["w"] for x in inc) / W, 3), "n": len(inc)}
    order = sorted(share, key=lambda n: (-share[n]["share"], -share[n]["n"], n))
    core_crafts = [n for n in order if share[n]["share"] >= CORE and craftable(n)]
    arch_out[a] = {
        "cls": CLASS_OF.get(a, "?"), "lists": [{k: x[k] for k in ("id", "level", "wr", "games", "dust")} | {"cards": x["cards"]} for x in ls],
        "games": games, "w": W, "wr": round(sum(x["wr"] * x["games"] for x in ls) / games, 1),
        "dust": int(statistics.median(x["dust"] for x in ls)),
        "order": order, "share": share,
        "coreCrafts": core_crafts, "coreCraftDust": sum(dust_of(n) for n in core_crafts),
    }

# Black Empire epics and legendaries, scored by the weight of the lists that run them
be_all = json.load(open(os.path.join(HERE, "be_epic_leg.json"), encoding="utf-8"))
total_w = sum(x["w"] for x in lists)
be_out = []
for c in be_all:
    n = c["name"]
    w = sum(x["w"] for x in lists if n in x["cards"])
    decks = []
    for a, A in arch_out.items():
        s = A["share"].get(n)
        if not s:
            continue
        needs = [m for m in A["coreCrafts"] if m != n]
        often = [m for m in A["order"] if FLEX <= A["share"][m]["share"] < CORE and craftable(m) and m != n]
        decks.append({"arch": a, "share": s["share"], "n": s["n"], "of": len(A["lists"]), "wr": A["wr"],
                      "w": A["w"], "needs": needs, "needsDust": sum(dust_of(m) for m in needs), "often": often})
    decks.sort(key=lambda d: -d["share"] * d["w"])
    best = max((d["share"] for d in decks), default=0)
    score = 100 * w / total_w
    strong_core = score >= 5 and any(d["share"] >= CORE and d["of"] >= 3 and d["wr"] >= 56 for d in decks)
    if n in TRAP:
        verdict = "skip"
    elif strong_core:
        verdict = "craft"
    elif best >= CORE:
        verdict = "niche"
    elif best >= FLEX:
        verdict = "optional"
    elif decks:
        verdict = "wait"
    else:
        verdict = "unplayed"
    be_out.append({"name": n, "rarity": c["rarity"], "cls": c["cls"], "dust": dust_of(n) if n in cards else DUST[c["rarity"]] * (1 if c["rarity"] == "LEGENDARY" else 2),
                   "lists": sum(1 for x in lists if n in x["cards"]), "score": round(score, 1),
                   "verdict": verdict, "trap": TRAP.get(n), "decks": decks})
be_out.sort(key=lambda b: -b["score"])

for c in be_all:  # tiles for unplayed cards too
    cards.setdefault(c["name"], {"id": c["id"], "rarity": c["rarity"], "set": "BE", "setName": "Black Empire",
                                 "cls": c["cls"], "cost": c["cost"], "collectible": True})

data = {"cards": cards, "archetypes": arch_out, "be": be_out,
        "totals": {"lists": len(lists), "games": sum(x["games"] for x in lists),
                   "d4": sum(1 for x in lists if x["level"] != "Top 5k"), "t5k": sum(1 for x in lists if x["level"] == "Top 5k")}}

if __name__ == "__main__" and "--summary" in sys.argv:
    for b in be_out:
        if b["verdict"] == "unplayed":
            continue
        print(f'{b["verdict"]:<8} {b["score"]:>5} {b["name"]:<28} {b["lists"]:>3} lists')
        for d in b["decks"][:4]:
            print(f'           {d["arch"]:<24} {d["share"]:.0%} ({d["n"]}/{d["of"]}) needs: {", ".join(d["needs"])} [{d["needsDust"]}]')
    sys.exit()

tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
render = lambda d: tpl.replace("/*__DATA__*/null", json.dumps(d, ensure_ascii=False).replace("</", "<\\/"))
page = render(data)

# artifact version: tiles inlined as data URIs, and the viewer supplies the document skeleton
tile_dir = os.path.join(PROJ, "site", "black-empire-census", "tiles")
inline = {c["id"]: "data:image/webp;base64," + base64.b64encode(open(os.path.join(tile_dir, c["id"] + ".webp"), "rb").read()).decode()
          for c in cards.values() if os.path.exists(os.path.join(tile_dir, c["id"] + ".webp"))}
open(os.path.join(HERE, "black-empire-census.html"), "w", encoding="utf-8").write(render(data | {"tiles": inline}))
head, _, rest = page.partition('<div class="wrap">')
standalone = ('<!doctype html>\n<html lang="en">\n<head>\n'
              '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
              + head + '<style>body{margin:0}</style>\n</head>\n<body>\n<div class="wrap">' + rest + "\n</body>\n</html>\n")
open(os.path.join(PROJ, "site", "black-empire-census", "index.html"), "w", encoding="utf-8").write(standalone)
open(os.path.join(HERE, "tile_ids.txt"), "w", newline="\n").write("\n".join(sorted({c["id"] for c in cards.values()})) + "\n")
print(len(cards), "cards,", len(arch_out), "archetypes")
