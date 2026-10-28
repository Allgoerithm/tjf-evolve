#!/usr/bin/env python3
"""Build the participant repository: everything needed for the exercises,
nothing that reveals the heldout split.

  uv run python scripts/package_participant.py OUTPUT_DIR [--force] [--zip] [--git]

Only the files and folders listed in INCLUDE are copied (an allowlist, so
new instructor files stay out by default). From queries/ only the dev and
validation profiles are copied. Left out on purpose: heldout/ (heldout ids
and labels), the 40 heldout profiles, PLAN.md (instructor notes), the data
generators and scripts/ (they could regenerate the heldout labels), runs,
caches, .env and the leaderboard database.

After copying, every text file of the package is scanned for heldout profile
ids and for the heldout file; the script fails if anything turns up.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Paths relative to the repo root. Directories are copied recursively.
INCLUDE = [
    ".env.example",
    ".gitignore",
    "CVs",
    "data/qrels.json",
    "data/splits.json",
    "docker-compose.yml",
    "evolve/configs",
    "evolve/evaluator.py",
    "evolve/initial_prompt.txt",
    "evolve/meta/templates",
    "participant_instructions.md",
    "pyproject.toml",
    "uv.lock",
    "src/evolve_demo",
    "tests",
]
SKIP_NAMES = {"__pycache__", ".DS_Store"}
SKIP_SUFFIXES = (".pyc",)

README = """# tjf-evolve: evolving query-rewriting prompts

Workshop material. Start with [participant_instructions.md](participant_instructions.md).
"""


def ignore(_dir, names):
    return [n for n in names if n in SKIP_NAMES or n.endswith(SKIP_SUFFIXES)]


def copy(rel, out):
    src, dst = os.path.join(ROOT, rel), os.path.join(out, rel)
    if not os.path.exists(src):
        sys.exit(f"missing in the repo: {rel}")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.isdir(src):
        shutil.copytree(src, dst, ignore=ignore)
    else:
        shutil.copy2(src, dst)


def participant_profile_ids():
    with open(os.path.join(ROOT, "data", "splits.json"), encoding="utf-8") as f:
        splits = json.load(f)
    return splits["dev"] + splits["validation"]


def heldout_ids():
    with open(os.path.join(ROOT, "heldout", "heldout.json"), encoding="utf-8") as f:
        return json.load(f)["queries"]


def scan_for_leaks(out, forbidden_ids):
    """Fail if any heldout id, heldout profile or the heldout folder ends up in the package."""
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, forbidden_ids)) + r")\b")
    problems = []
    for dirpath, _dirs, files in os.walk(out):
        if os.path.basename(dirpath) == "heldout":
            problems.append(f"{os.path.relpath(dirpath, out)}/ exists")
        for name in files:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, out)
            if os.path.splitext(name)[0] in forbidden_ids:
                problems.append(f"{rel}: heldout profile file")
                continue
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
            except (UnicodeDecodeError, OSError):
                continue   # binary files cannot contain the ids in readable form
            m = pattern.search(text)
            if m:
                problems.append(f"{rel}: mentions heldout profile {m.group(1)}")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("output_dir")
    ap.add_argument("--force", action="store_true", help="replace OUTPUT_DIR if it exists")
    ap.add_argument("--zip", action="store_true", help="also write OUTPUT_DIR.zip")
    ap.add_argument("--git", action="store_true", help="initialise a git repository with one commit")
    args = ap.parse_args(argv)

    out = os.path.abspath(args.output_dir)
    if out == ROOT or out.startswith(ROOT + os.sep):
        sys.exit("OUTPUT_DIR must be outside the repository")
    if os.path.exists(out):
        if not args.force:
            sys.exit(f"{out} exists; use --force to replace it")
        shutil.rmtree(out)

    for rel in INCLUDE:
        copy(rel, out)
    profiles = participant_profile_ids()
    for pid in profiles:
        copy(os.path.join("queries", pid + ".txt"), out)
    with open(os.path.join(out, "README.md"), "w", encoding="utf-8") as f:
        f.write(README)

    problems = scan_for_leaks(out, heldout_ids())
    if problems:
        shutil.rmtree(out)
        sys.exit("heldout data found, package removed:\n  " + "\n  ".join(problems))

    if args.git:
        subprocess.run(["git", "init", "-q", out], check=True)
        subprocess.run(["git", "-C", out, "add", "-A"], check=True)
        subprocess.run(["git", "-C", out, "commit", "-q", "-m", "Workshop material"], check=True)
    if args.zip:
        shutil.make_archive(out, "zip", os.path.dirname(out), os.path.basename(out))

    n_files = sum(len(files) for _d, _s, files in os.walk(out) if ".git" not in _d.split(os.sep))
    print(json.dumps({"output_dir": out, "files": n_files, "profiles": len(profiles),
                      "cvs": len(os.listdir(os.path.join(out, "CVs"))), "leak_check": "passed",
                      "zip": out + ".zip" if args.zip else None}, indent=1))


if __name__ == "__main__":
    main()
