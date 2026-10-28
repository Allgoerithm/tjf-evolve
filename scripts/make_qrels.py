#!/usr/bin/env python3
"""Compute the relevance labels (qrels) and the dev/validation/heldout split.

Reads CVs/ and queries/, labels every (profile, CV) pair with
src/evolve_demo/labels.py and writes:

  data/splits.json    dev + validation query ids              (participants)
  data/qrels.json     labels for dev and validation
                                                              (participants)
  heldout/heldout.json  heldout query ids and labels
                                                              (leaderboard server ONLY)

Only pairs with label 1 or 2 are stored; every other pair is 0. CV ids are the
file names without ".txt". The split is stratified by archetype (the file name
prefix of a profile) and fixed by SEED.
"""
import collections
import glob
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from evolve_demo import labels  # noqa: E402

SEED = 2026
SHARES = {"dev": 40, "validation": 20, "heldout": 40}   # out of 100 profiles


def stem(path):
    return os.path.splitext(os.path.basename(path))[0]


def make_split(query_ids):
    rng = random.Random(SEED)
    groups = collections.defaultdict(list)
    for qid in query_ids:
        groups[qid.rsplit("_", 1)[0]].append(qid)
    assert len(query_ids) == sum(SHARES.values())
    quota, split = dict(SHARES), {name: [] for name in SHARES}
    leftovers = []
    for _slug, ids in sorted(groups.items()):
        rng.shuffle(ids)
        counts = {name: int(len(ids) * share / len(query_ids)) for name, share in SHARES.items()}
        taken = 0
        for name, c in counts.items():
            split[name] += ids[taken:taken + c]
            quota[name] -= c
            taken += c
        leftovers += ids[taken:]
    rng.shuffle(leftovers)
    for qid in leftovers:   # the few profiles left over by rounding fill the open quotas
        name = max(quota, key=quota.get)
        split[name].append(qid)
        quota[name] -= 1
    assert all(v == 0 for v in quota.values()), quota
    return {name: sorted(ids) for name, ids in split.items()}


def main():
    cvs = {stem(p): labels.parse_cv(open(p, encoding="utf-8").read())
           for p in sorted(glob.glob(os.path.join(ROOT, "CVs", "*.txt")))}
    queries = {stem(p): labels.parse_query(open(p, encoding="utf-8").read())
               for p in sorted(glob.glob(os.path.join(ROOT, "queries", "*.txt")))}

    qrels, ceiling = {}, {}
    for qid, q in queries.items():
        all_labels = {cid: labels.label(cv, q) for cid, cv in cvs.items()}
        qrels[qid] = {cid: l for cid, l in sorted(all_labels.items()) if l}
        ceiling[qid] = labels.ceiling(all_labels)

    split = make_split(list(queries))

    def part(names):
        ids = sorted(i for n in names for i in split[n])
        return {"top_k": labels.TOP_K, "labels": {i: qrels[i] for i in ids}}

    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "heldout"), exist_ok=True)
    dump = lambda path, obj: open(os.path.join(ROOT, path), "w", encoding="utf-8").write(
        json.dumps(obj, indent=1, sort_keys=True) + "\n")
    dump("data/splits.json", {"seed": SEED, "dev": split["dev"], "validation": split["validation"]})
    dump("data/qrels.json", part(["dev", "validation"]))
    dump("heldout/heldout.json", {"queries": split["heldout"], **part(["heldout"])})

    for name, ids in split.items():
        arch = collections.Counter(i.rsplit("_", 1)[0] for i in ids)
        print(f"{name:10} {len(ids)} profiles, reachable score (of {labels.MAX_SCORE} points): "
              f"{sorted(collections.Counter(round(ceiling[i] * labels.MAX_SCORE) for i in ids).items())}, "
              f"mean ceiling {sum(ceiling[i] for i in ids) / len(ids):.1%}")
        print("           ", dict(sorted(arch.items())))


if __name__ == "__main__":
    main()
