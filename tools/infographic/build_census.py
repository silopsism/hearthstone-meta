"""Build the craft-guide data from full deck lists, then render the page.

Each archetype is treated as one deck: its lists are variants, and a card's
share is the weighted fraction of those variants that run it.
Weight per list = games * (winrate - 50).

Every collectible epic and legendary in Standard gets a tier:
  core   - core in a playable deck and a regular in at least one other deck (any class)
  solid  - core in one playable deck
  fringe - a flex pick somewhere, or core only in a one-list deck
  trash  - barely played or not played at all
  free   - costs no dust (Core set, events, reward tracks, pack or quest grants)

Usage: python tools/infographic/build_census.py <path to HearthstoneJSON cards.json (all cards)>
"""
import base64, csv, json, os, re, statistics, sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, "..", ".."))
TILES = os.path.join(PROJ, "site", "black-empire-census", "tiles")
sys.path.insert(0, PROJ)
from analyze_decks import CLASS_OF  # noqa: E402

CORE, SOLID = 0.8, 0.3
CORE_MIN_WEIGHT = 2.0     # % of all weighted play a "core" card must reach
PLAYABLE_LISTS = 2        # a deck needs this many lists to count as playable
DUST = {"LEGENDARY": 1600, "EPIC": 400, "RARE": 100, "COMMON": 40}
SETS = [  # Standard, newest first: (code, badge, name)
    ("BE", "BE", "Reign of the Black Empire"),
    ("TIME_TRAVEL", "TW", "Across the Timeways"),
    ("ESCAPEFROM_VIOLET_HOLD", "VH", "Escape from Violet Hold"),
    ("THE_LOST_CITY", "UG", "The Lost City of Un'Goro"),
    ("EMERALD_DREAM", "ED", "Into the Emerald Dream"),
    ("CATACLYSM", "CATA", "Cataclysm"),
    ("CORE", "CORE", "Core"),
    ("EVENT", "EVT", "Event"),
]
STANDARD = {s[0] for s in SETS}
SET_BADGE = {s[0]: s[1] for s in SETS}
SET_NAME = {s[0]: s[2] for s in SETS}
FORCE_FRINGE = {"N'Zoth, Dream's End": "Played, but plain BFU Handbuff DK without it wins more at both levels."}

allc = json.load(open(sys.argv[1], encoding="utf-8"))


def rank(c):  # which printing of a name to use: Standard collectible first
    return (not c.get("collectible"), c.get("set") not in STANDARD, c.get("set") == "HERO_SKINS")


by_name = {}
for c in allc:
    p = by_name.get(c["name"])
    if p is None or rank(c) < rank(p):
        by_name[c["name"]] = c


def free_reason(c):
    """Why a collectible card costs no dust, or None. Golden-only rewards don't count."""
    if c.get("set") == "CORE":
        return "Core set: free for every player"
    if c.get("howToEarn"):
        return re.sub(r"</?i>", "", c["howToEarn"])
    if c.get("set") == "EVENT":
        return "Event reward"
    return None


lists = []
for r in csv.DictReader(open(os.path.join(PROJ, "data", "lists_2026-10-24.csv"), encoding="utf-8")):
    wr, g = float(r["winrate"]), int(r["games"])
    lists.append({"id": r["deck"], "level": r["level"], "arch": r["archetype"], "wr": wr, "games": g,
                  "dust": int(r["dust"]), "w": g * max(wr - 50, 0), "cards": [x for x in r["cards"].split(";") if x]})

pool = {c["name"]: c for c in allc
        if c.get("collectible") and c.get("set") in STANDARD and c.get("rarity") in ("EPIC", "LEGENDARY")
        and by_name[c["name"]] is c}

def card_text(c):
    """Card text as small safe HTML: keep <b>, <i> and line breaks, drop the rest of the markup."""
    t = (c.get("text") or "").replace("[x]", "").replace("\n", "<br>")
    t = re.sub(r"[$#](\d+)", r"\1", t)
    return re.sub(r"<(?!/?(?:b|i|br)\b)[^>]*>", "", t).strip()


def card_kind(c):
    words = [w.title() for w in (c.get("races") or ([c["race"]] if c.get("race") else []))]
    if c.get("spellSchool"):
        words.append(c["spellSchool"].title())
    return " · ".join([(c.get("type") or "").title()] + words)


cards = {}
for n in {n for L in lists for n in L["cards"]} | set(pool):
    c = by_name[n]
    second = c.get("durability") if c.get("durability") is not None else c.get("health")
    stats = [x for x in (c.get("attack"), second) if x is not None] if second is not None else []
    cards[n] = {"id": c["id"], "rarity": c.get("rarity") or "FREE", "set": c.get("set"),
                "badge": SET_BADGE.get(c.get("set"), (c.get("set") or "?")[:4]), "setName": SET_NAME.get(c.get("set"), c.get("set")),
                "cls": c.get("cardClass"), "cost": c.get("cost"), "collectible": bool(c.get("collectible")),
                "free": free_reason(c) if c.get("collectible") else None,
                "text": card_text(c), "kind": card_kind(c), "stats": stats}


def craftable(n):
    c = cards[n]
    return c["collectible"] and c["rarity"] in ("EPIC", "LEGENDARY") and not c["free"]


def dust_of(n):
    r = cards[n]["rarity"]
    return DUST.get(r, 0) * (1 if r == "LEGENDARY" else 2)


archs = defaultdict(list)
for L in lists:
    archs[L["arch"]].append(L)

arch_out = {}
for a, ls in archs.items():
    ls.sort(key=lambda x: -x["wr"])
    W = sum(x["w"] for x in ls) or 1
    games = sum(x["games"] for x in ls)
    share = {n: {"share": round(sum(x["w"] for x in ls if n in x["cards"]) / W, 3), "n": sum(1 for x in ls if n in x["cards"])}
             for n in {n for x in ls for n in x["cards"]}}
    order = sorted(share, key=lambda n: (-share[n]["share"], -share[n]["n"], n))
    core_crafts = [n for n in order if share[n]["share"] >= CORE and craftable(n)]
    arch_out[a] = {
        "cls": CLASS_OF.get(a, "?"),
        "lists": [{k: x[k] for k in ("id", "level", "wr", "games", "dust")} | {"cards": x["cards"]} for x in ls],
        "games": games, "w": W, "wr": round(sum(x["wr"] * x["games"] for x in ls) / games, 1),
        "dust": int(statistics.median(x["dust"] for x in ls)), "order": order, "share": share,
        "coreCrafts": core_crafts, "coreCraftDust": sum(dust_of(n) for n in core_crafts),
    }

total_w = sum(x["w"] for x in lists)
crafts = []
for n in pool:
    c = cards[n]
    w = sum(x["w"] for x in lists if n in x["cards"])
    score = 100 * w / total_w
    decks = []
    for a, A in arch_out.items():
        s = A["share"].get(n)
        if not s:
            continue
        needs = [m for m in A["coreCrafts"] if m != n]
        decks.append({"arch": a, "share": s["share"], "n": s["n"], "of": len(A["lists"]), "wr": A["wr"],
                      "w": A["w"], "needs": needs, "needsDust": sum(dust_of(m) for m in needs)})
    decks.sort(key=lambda d: -d["share"] * d["w"])
    core_in = [d for d in decks if d["share"] >= CORE and d["of"] >= PLAYABLE_LISTS]
    solid_in = [d for d in decks if d["share"] >= SOLID and d["of"] >= PLAYABLE_LISTS]
    if c["free"]:
        tier = "free"
    elif n in FORCE_FRINGE:
        tier = "fringe"
    elif core_in and len(solid_in) >= 2 and score >= CORE_MIN_WEIGHT:
        tier = "core"
    elif core_in:
        tier = "solid"
    elif any(d["share"] >= SOLID for d in decks):
        tier = "fringe"
    else:
        tier = "trash"
    crafts.append({"name": n, "set": c["set"], "rarity": c["rarity"], "cls": c["cls"], "dust": dust_of(n),
                   "free": c["free"], "score": round(score, 1), "tier": tier, "note": FORCE_FRINGE.get(n),
                   "lists": {"d4": sum(1 for x in lists if n in x["cards"] and x["level"] != "Top 5k"),
                             "t5k": sum(1 for x in lists if n in x["cards"] and x["level"] == "Top 5k")},
                   "classes": len({arch_out[d["arch"]]["cls"] for d in solid_in}), "decks": decks})
TIER_ORDER = {"core": 0, "solid": 1, "fringe": 2, "trash": 3, "free": 4}
crafts.sort(key=lambda b: (TIER_ORDER[b["tier"]], b["rarity"] != "LEGENDARY", -b["score"], b["name"]))

# per-level shares of every epic and legendary, for the Classes tab
levels = {}
for key, label in (("d4", "Diamond 4-1"), ("t5k", "Top 5k")):
    ls = [x for x in lists if x["level"] == label]
    lv = {"lists": len(ls), "games": sum(x["games"] for x in ls), "archetypes": {}}
    for a in {x["arch"] for x in ls}:
        al = [x for x in ls if x["arch"] == a]
        W = sum(x["w"] for x in al) or 1
        games = sum(x["games"] for x in al)
        lv["archetypes"][a] = {
            "cls": CLASS_OF.get(a, "?"), "lists": len(al), "games": games, "w": W,
            "wr": round(sum(x["wr"] * x["games"] for x in al) / games, 1),
            "cards": {n: {"n": sum(1 for x in al if n in x["cards"]),
                          "share": round(sum(x["w"] for x in al if n in x["cards"]) / W, 2)}
                      for n in {n for x in al for n in x["cards"] if n in pool}},
        }
    levels[key] = lv
meta = list(csv.DictReader(open(os.path.join(PROJ, "data", "archetypes_2026-10-24.csv"), encoding="utf-8")))

data = {"cards": cards, "archetypes": arch_out, "crafts": crafts, "levels": levels, "meta": meta,
        "sets": [{"code": s[0], "badge": s[1], "name": s[2]} for s in SETS],
        "totals": {"lists": len(lists), "games": sum(x["games"] for x in lists),
                   "d4": sum(1 for x in lists if x["level"] != "Top 5k"), "t5k": sum(1 for x in lists if x["level"] == "Top 5k")}}

if "--summary" in sys.argv:
    for t in TIER_ORDER:
        sel = [b for b in crafts if b["tier"] == t and (b["lists"]["d4"] + b["lists"]["t5k"])]
        print(f"\n== {t} ({len(sel)} played)")
        for b in sel[:40]:
            ds = ", ".join(f'{d["arch"]} {d["share"]:.0%}' for d in b["decks"] if d["share"] >= SOLID)
            print(f'  {b["rarity"][0]} {SET_BADGE[b["set"]]:<4} {b["score"]:>5} {b["name"]:<30} {ds}')
    sys.exit()

open(os.path.join(HERE, "tile_ids.txt"), "w", newline="\n").write("\n".join(sorted({c["id"] for c in cards.values()})) + "\n")
if "--ids" in sys.argv:
    sys.exit()

tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
render = lambda d: tpl.replace("/*__DATA__*/null", json.dumps(d, ensure_ascii=False).replace("</", "<\\/"))
page = render(data)
# artifact version: tiles inlined as data URIs, and the viewer supplies the document skeleton
inline = {c["id"]: "data:image/webp;base64," + base64.b64encode(open(os.path.join(TILES, c["id"] + ".webp"), "rb").read()).decode()
          for c in cards.values() if os.path.exists(os.path.join(TILES, c["id"] + ".webp"))}
open(os.path.join(HERE, "black-empire-census.html"), "w", encoding="utf-8").write(render(data | {"tiles": inline}))
head, _, rest = page.partition('<div class="wrap">')
standalone = ('<!doctype html>\n<html lang="en">\n<head>\n'
              '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
              + head + '<style>body{margin:0}</style>\n</head>\n<body>\n<div class="wrap">' + rest + "\n</body>\n</html>\n")
open(os.path.join(PROJ, "site", "black-empire-census", "index.html"), "w", encoding="utf-8").write(standalone)
print(len(cards), "cards,", len(arch_out), "archetypes,", len(crafts), "Standard epics and legendaries")
