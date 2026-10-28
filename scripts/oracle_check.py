#!/usr/bin/env python3
"""Sanity check of index, labels and metric, without any LLM.

Builds simple boolean queries straight from the structured search profiles
("what a perfect, rule-following rewriter could do") and scores them with the
top-5 metric. The numbers calibrate the task: they must be clearly above 0 and
clearly below 100%, so that evolved prompts have room to improve.
"""
import glob
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from evolve_demo import labels, opensearch as osr  # noqa: E402


def phrase(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def strict_and(q):
    return " AND ".join(phrase(s) for s in q["must"])


def must_or(q):
    return " OR ".join(phrase(s) for s in q["must"])


def weighted_or(q):
    parts = [phrase(s) + "^3" for s in q["must"]] + [phrase(s) for s in q["nice"]]
    parts += [phrase(c) for c in q["certs"]]
    return " OR ".join(parts)


def weighted_or_experience(q):
    return f"({weighted_or(q)}) AND years_experience:[{max(q['min_years'] - 1, 0)} TO *]"


STRATEGIES = {
    "all must-haves, AND": strict_and,
    "must-haves, OR": must_or,
    "must^3 + nice-to-haves + certs, OR": weighted_or,
    "... and min. experience filter": weighted_or_experience,
}


def main():
    osr.wait_until_ready()
    parts = [json.load(open(os.path.join(ROOT, "data/qrels.json")))["labels"],
             json.load(open(os.path.join(ROOT, "heldout/heldout.json")))["labels"]]
    qrels = {k: v for p in parts for k, v in p.items()}
    ceiling = statistics.mean(labels.ceiling(v) for v in qrels.values())
    print(f"{len(qrels)} profiles; metric = points in top {labels.TOP_K} / {labels.MAX_SCORE}; "
          f"best reachable on average: {ceiling:.1%}\n")
    for name, build in STRATEGIES.items():
        scores, empty = [], 0
        for qid in qrels:
            q = labels.parse_query(open(os.path.join(ROOT, "queries", qid + ".txt"), encoding="utf-8").read())
            ranked = osr.search_boolean(build(q))
            empty += not ranked
            scores.append(labels.score(ranked, qrels[qid]))
        print(f"{name:40} mean {statistics.mean(scores):6.1%}   median {statistics.median(scores):6.1%}   "
              f"zero {sum(s == 0 for s in scores):3}   no results {empty:3}")


if __name__ == "__main__":
    main()
