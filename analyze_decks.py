"""Summarise Black Empire epic/legendary inclusion per archetype from a deck CSV.

Each deck is weighted by games * (winrate - 50), so well-sampled, high-winrate
lists count for more than small or marginal ones.

Usage: python analyze_decks.py data/decks_diamond_2026-10-24.csv
"""
import csv
import sys
from collections import defaultdict

CLASS_OF = {
    "Zoolock": "Warlock", "Shredslock": "Warlock", "C'Thun Warlock": "Warlock",
    "Harold C'Thun Warlock": "Warlock", "XL Rafaamlock": "Warlock", "Demon Warlock": "Warlock",
    "Warlock (header hidden)": "Warlock",
    "C'Thun DH": "Demon Hunter", "Void C'Thun DH": "Demon Hunter",
    "Zee C'Thun Shaman": "Shaman", "Mug Shaman": "Shaman", "Summoner Mage": "Mage",
    "BFU Handbuff DK": "Death Knight", "BFU N'Zoth Handbuff DK": "Death Knight", "Unholy DK": "Death Knight",
    "Pure Paladin": "Paladin", "Holy Paladin": "Paladin",
    "Egg Priest": "Priest", "Thief Priest": "Priest",
    "AYAYA Rogue": "Rogue", "C'Thun Druid": "Druid",
    "Egg Warrior": "Warrior", "Dragon Warrior": "Warrior", "Pirate Warrior": "Warrior",
}


def tier(share):
    return "core" if share >= 0.8 else "flex" if share >= 0.3 else "experimental"


def main(path):
    decks = []
    for row in csv.DictReader(open(path, encoding="utf-8")):
        wr, games = float(row["winrate"]), int(row["games"])
        decks.append({
            "arch": row["archetype"], "wr": wr, "games": games,
            "weight": games * max(wr - 50, 0),
            "cards": {c for c in row["be_epic_legendary"].split(";") if c},
        })

    by_arch = defaultdict(list)
    for d in decks:
        by_arch[d["arch"]].append(d)

    by_class = defaultdict(list)
    for arch, ds in by_arch.items():
        by_class[CLASS_OF.get(arch, "?")].append(arch)

    for cls in sorted(by_class, key=lambda c: -sum(d["games"] for a in by_class[c] for d in by_arch[a])):
        print(f"\n=== {cls}")
        for arch in sorted(by_class[cls], key=lambda a: -sum(d["games"] for d in by_arch[a])):
            ds = by_arch[arch]
            games = sum(d["games"] for d in ds)
            wsum = sum(d["weight"] for d in ds) or 1
            avg_wr = sum(d["wr"] * d["games"] for d in ds) / games
            print(f"  {arch}: {len(ds)} lists, {games} games, avg WR {avg_wr:.1f}")
            for card in sorted({c for d in ds for c in d["cards"]},
                               key=lambda c: -sum(d["weight"] for d in ds if c in d["cards"])):
                inc = [d for d in ds if card in d["cards"]]
                exc = [d for d in ds if card not in d["cards"]]
                share = sum(d["weight"] for d in inc) / wsum
                wr_in = sum(d["wr"] * d["games"] for d in inc) / sum(d["games"] for d in inc)
                wr_out = (sum(d["wr"] * d["games"] for d in exc) / sum(d["games"] for d in exc)) if exc else None
                delta = f"{wr_in - wr_out:+.1f}" if wr_out is not None else "n/a"
                print(f"    {tier(share):<12} {card:<32} {len(inc)}/{len(ds)} lists, "
                      f"weighted {share:4.0%}, WR with {wr_in:.1f} (vs without {delta})")


if __name__ == "__main__":
    main(sys.argv[1])
