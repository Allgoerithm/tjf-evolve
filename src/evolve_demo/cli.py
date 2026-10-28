"""evolve-eval: command line wrapper around the core evaluation.

Every command prints exactly one JSON object on stdout, so scripts and agents
(e.g. oh-my-pi) can call it as a tool. Progress and hints go to stderr.

  evolve-eval check                                  setup check: OpenSearch, index, LLM
  evolve-eval index                                  (re)load the CVs into OpenSearch
  evolve-eval run PROMPT_FILE [--split dev]          score a rewriting prompt ('-' = stdin)
  evolve-eval baseline [--split dev]                 score evolve/initial_prompt.txt
  evolve-eval submit PROMPT_FILE --name NAME [--wait] send prompt + meta-prompt + GA config
                                                     to the leaderboard (LEADERBOARD_URL,
                                                     LEADERBOARD_TOKEN)

Exit codes: 0 ok, 1 invalid input (prompt, arguments), 2 setup problem
(OpenSearch or LLM not reachable, missing key). On failure the JSON object
is {"error": "...", "kind": "input" | "setup"}.
"""
import argparse
import glob
import json
import os
import sys
import time

import requests

from . import evaluate, llm, opensearch as osr

BASELINE = os.path.join(evaluate.ROOT, "evolve", "initial_prompt.txt")
META_DIR = os.path.join(evaluate.ROOT, "evolve", "meta", "templates")
GA_CONFIG = os.path.join(evaluate.ROOT, "evolve", "configs", "evolve.yaml")
PARTICIPANT_SPLITS = ("dev", "validation")


class JSONArgumentParser(argparse.ArgumentParser):
    """Argument errors as JSON with exit code 1, like every other input error."""

    def error(self, message):
        emit({"error": f"{self.prog}: {message}", "kind": "input"})
        sys.exit(1)


class CLIError(Exception):
    def __init__(self, message, kind):
        super().__init__(message)
        self.kind = kind


def emit(obj):
    print(json.dumps(obj, indent=1, ensure_ascii=False))


def read_prompt(path):
    if path == "-":
        return sys.stdin.read()
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        raise CLIError(f"cannot read file: {e}", "input")


def cmd_check(args):
    result = {"opensearch_url": osr.URL, "index": osr.INDEX}
    require_opensearch()
    r = requests.get(f"{osr.URL}/{osr.INDEX}/_count", timeout=10)
    if r.status_code == 404:
        raise CLIError(f"index '{osr.INDEX}' missing; create it with: evolve-eval index", "setup")
    r.raise_for_status()
    result["indexed_cvs"] = r.json()["count"]
    n_files = len(glob.glob(os.path.join(evaluate.ROOT, "CVs", "*.txt")))
    if result["indexed_cvs"] != n_files:
        raise CLIError(f"index holds {result['indexed_cvs']} CVs but CVs/ has {n_files}; run: evolve-eval index",
                       "setup")
    cfg = llm.settings()
    result.update(provider=cfg["provider"], model=cfg["model"], endpoint=cfg["base_url"])
    try:
        models = llm.list_models()
    except llm.LLMError as e:
        raise CLIError(str(e), "setup")
    if cfg["model"] not in models:
        raise CLIError(f"model {cfg['model']} not offered by {cfg['base_url']}", "setup")
    t = time.time()
    try:
        llm.complete("Answer with the single word: ok", max_tokens=256)
    except llm.LLMError as e:
        raise CLIError(str(e), "setup")
    result["llm_seconds"] = round(time.time() - t, 1)
    result["ok"] = True
    return result


def cmd_index(args):
    try:
        osr.wait_until_ready(timeout=args.wait)
    except Exception:
        raise CLIError(f"OpenSearch not reachable at {osr.URL}; start it with: docker compose up -d --wait", "setup")
    paths = sorted(glob.glob(os.path.join(evaluate.ROOT, "CVs", "*.txt")))
    if args.if_needed:
        r = requests.get(f"{osr.URL}/{osr.INDEX}/_count", timeout=10)
        if r.status_code == 200 and r.json()["count"] == len(paths):
            return {"indexed_cvs": len(paths), "index": osr.INDEX, "opensearch_url": osr.URL, "skipped": True}
    docs = {}
    for path in paths:
        with open(path, encoding="utf-8") as f:
            docs[os.path.splitext(os.path.basename(path))[0]] = osr.cv_document(f.read())
    osr.recreate_index()
    return {"indexed_cvs": osr.bulk_index(docs), "index": osr.INDEX, "opensearch_url": osr.URL}


def require_opensearch():
    try:
        requests.get(osr.URL, timeout=5).raise_for_status()
    except requests.RequestException:
        raise CLIError(f"OpenSearch not reachable at {osr.URL}; start it with: docker compose up -d --wait", "setup")


def score(prompt, args):
    if not llm.settings()["api_key"]:
        raise CLIError(f"no API key: set {llm.settings()['key_env']}", "setup")
    require_opensearch()   # fail before spending LLM calls
    print(f"scoring on split '{args.split}' ...", file=sys.stderr)
    try:
        result = evaluate.evaluate_prompt(prompt, args.split, workers=args.workers, limit=args.limit)
    except evaluate.PromptError as e:
        raise CLIError(f"invalid prompt: {e}", "input")
    except requests.RequestException as e:
        raise CLIError(f"OpenSearch problem during scoring: {type(e).__name__}", "setup")
    if result["n_errors"] == result["n_profiles"]:
        first = result["per_profile"][0]["error"]
        if first.startswith("LLM error"):   # every call failed: a setup problem, not a bad prompt
            raise CLIError(first, "setup")
    if not args.details:
        result.pop("per_profile")
    return result


def cmd_run(args):
    return score(read_prompt(args.prompt_file), args)


def cmd_baseline(args):
    result = score(read_prompt(BASELINE), args)
    result["prompt_file"] = os.path.relpath(BASELINE, evaluate.ROOT)
    return result


def read_meta_dir(path):
    if not os.path.isdir(path):
        raise CLIError(f"meta-prompt directory not found: {path}", "input")
    meta = {}
    for name in sorted(os.listdir(path)):
        full = os.path.join(path, name)
        if os.path.isfile(full) and name.endswith((".txt", ".json")):
            with open(full, encoding="utf-8") as f:
                meta[name] = f.read()
    return meta


def cmd_submit(args):
    server = (args.server or os.environ.get("LEADERBOARD_URL", "")).rstrip("/")
    token = os.environ.get("LEADERBOARD_TOKEN", "")
    if not server:
        raise CLIError("no leaderboard address: set LEADERBOARD_URL or use --server", "setup")
    if not token:
        raise CLIError("no workshop token: set LEADERBOARD_TOKEN", "setup")
    prompt = read_prompt(args.prompt_file)
    try:
        evaluate.check_prompt(prompt)
    except evaluate.PromptError as e:
        raise CLIError(f"invalid prompt: {e}", "input")
    bundle = {"participant": args.name, "rewriting_prompt": prompt, "meta_prompt": read_meta_dir(args.meta_dir),
              "ga_config": read_prompt(args.config)}
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.post(f"{server}/submit", json=bundle, headers=headers, timeout=30)
    except requests.RequestException:
        raise CLIError(f"leaderboard not reachable at {server}", "setup")
    if r.status_code == 401:
        raise CLIError("the leaderboard rejected the workshop token (LEADERBOARD_TOKEN)", "setup")
    if r.status_code >= 400:
        try:
            detail = r.json()["detail"]
        except (ValueError, KeyError):
            detail = r.text[:300]
        raise CLIError(f"submission rejected: {detail if isinstance(detail, str) else json.dumps(detail)}", "input")
    result = r.json()
    result["leaderboard"] = server + "/"
    if not args.wait:
        return result
    print(f"submitted as #{result['id']}; waiting for the score ...", file=sys.stderr)
    deadline = time.time() + args.wait_timeout
    while time.time() < deadline:
        time.sleep(5)
        try:
            state = requests.get(f"{server}/api/submissions/{result['id']}", timeout=30).json()
        except (requests.RequestException, ValueError):
            continue
        if state["status"] in ("done", "failed"):
            state["leaderboard"] = result["leaderboard"]
            return state
    raise CLIError(f"no score after {args.wait_timeout} s; check {result['leaderboard']}", "setup")


def add_scoring_args(p):
    p.add_argument("--split", default="dev", choices=PARTICIPANT_SPLITS)
    p.add_argument("--limit", type=int, help="only the first N profiles of the split (quick tests)")
    p.add_argument("--workers", type=int, default=8, help="parallel LLM calls (default 8)")
    p.add_argument("--details", action="store_true", help="include per-profile results (queries, hits, errors)")


def build_parser():
    ap = JSONArgumentParser(prog="evolve-eval", description="Evaluate query-rewriting prompts.")
    sub = ap.add_subparsers(dest="command", required=True, parser_class=JSONArgumentParser)
    sub.add_parser("check", help="check OpenSearch, index and LLM access").set_defaults(func=cmd_check)
    p = sub.add_parser("index", help="(re)load the CVs into OpenSearch")
    p.add_argument("--wait", type=int, default=180, help="seconds to wait for OpenSearch (default 180)")
    p.add_argument("--if-needed", action="store_true",
                   help="skip if the index already holds as many CVs as CVs/ (keeps running evaluations intact)")
    p.set_defaults(func=cmd_index)
    p = sub.add_parser("run", help="score a rewriting prompt")
    p.add_argument("prompt_file", help="file with the rewriting prompt, '-' for stdin; must contain {profile}")
    add_scoring_args(p)
    p.set_defaults(func=cmd_run)
    p = sub.add_parser("baseline", help="score the baseline prompt evolve/initial_prompt.txt")
    add_scoring_args(p)
    p.set_defaults(func=cmd_baseline)
    p = sub.add_parser("submit", help="submit a rewriting prompt to the leaderboard")
    p.add_argument("prompt_file", help="file with the rewriting prompt, e.g. evolve/runs/NAME/best/best_program.txt")
    p.add_argument("--name", required=True, help="your name on the leaderboard")
    p.add_argument("--meta-dir", default=META_DIR, help="meta-prompt templates to include (default evolve/meta/templates)")
    p.add_argument("--config", default=GA_CONFIG, help="GA config to include (default evolve/configs/evolve.yaml)")
    p.add_argument("--server", help="leaderboard address (default: LEADERBOARD_URL)")
    p.add_argument("--wait", action="store_true", help="wait until the submission is scored")
    p.add_argument("--wait-timeout", type=int, default=900, help="seconds to wait with --wait (default 900)")
    p.set_defaults(func=cmd_submit)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        emit(args.func(args))
    except CLIError as e:
        emit({"error": str(e), "kind": e.kind})
        sys.exit(1 if e.kind == "input" else 2)


if __name__ == "__main__":
    main()
