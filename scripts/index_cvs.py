#!/usr/bin/env python3
"""(Re)create the OpenSearch index and load all CVs from CVs/ (idempotent)."""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from evolve_demo import opensearch as osr  # noqa: E402


def main():
    osr.wait_until_ready()
    docs = {os.path.splitext(os.path.basename(p))[0]: osr.cv_document(open(p, encoding="utf-8").read())
            for p in sorted(glob.glob(os.path.join(ROOT, "CVs", "*.txt")))}
    osr.recreate_index()
    n = osr.bulk_index(docs)
    print(f"Indexed {n} CVs into '{osr.INDEX}' at {osr.URL}")


if __name__ == "__main__":
    main()
