"""Core evaluation: score a rewriting prompt on one split.

For every search profile of the split, the rewriting prompt (with the profile
text inserted at {profile}) goes to the LLM, the answer is run as a boolean
query_string against OpenSearch, and the top TOP_K CV ids are scored against
the relevance labels. No openevolve dependency: openevolve's evaluator, the CLI
and the leaderboard server all call evaluate_prompt().

  python -m evolve_demo.evaluate evolve/initial_prompt.txt --split dev
"""
import argparse
import concurrent.futures
import json
import os
import re
import statistics
import sys
import time

from . import labels, llm, opensearch as osr

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLACEHOLDER = "{profile}"
SPLITS = ("dev", "validation", "heldout")
MAX_PROMPT_CHARS = 20000


class PromptError(ValueError):
    """The rewriting prompt itself is unusable (no placeholder, too long)."""


def load_split(split, root=ROOT):
    """Profile ids and relevance labels {profile_id: {cv_id: 1|2}} of a split.
    The heldout split only exists on the leaderboard server."""
    if split not in SPLITS:
        raise ValueError(f"unknown split '{split}' (use one of {', '.join(SPLITS)})")
    if split == "heldout":
        path = os.path.join(root, "heldout", "heldout.json")
        if not os.path.isfile(path):
            raise FileNotFoundError("the heldout split is only available on the leaderboard server")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data["queries"], data["labels"]
    with open(os.path.join(root, "data", "splits.json"), encoding="utf-8") as f:
        ids = json.load(f)[split]
    with open(os.path.join(root, "data", "qrels.json"), encoding="utf-8") as f:
        qrels = json.load(f)["labels"]
    return ids, {qid: qrels[qid] for qid in ids}


def load_profile(profile_id, root=ROOT):
    with open(os.path.join(root, "queries", profile_id + ".txt"), encoding="utf-8") as f:
        return f.read()


def render(prompt, profile_text):
    """Insert the profile at {profile}. Plain replace, not str.format, so other
    braces in an evolved prompt are harmless."""
    return prompt.replace(PLACEHOLDER, profile_text)


def check_prompt(prompt):
    if PLACEHOLDER not in prompt:
        raise PromptError(f"the rewriting prompt must contain the placeholder {PLACEHOLDER}")
    if len(prompt) > MAX_PROMPT_CHARS:
        raise PromptError(f"the rewriting prompt is longer than {MAX_PROMPT_CHARS} characters")


_FENCE = re.compile(r"^```[a-zA-Z]*\s*\n?(.*?)\n?```$", re.S)


def extract_query(answer):
    """The query text of an LLM answer: strips whitespace and a surrounding
    Markdown code fence. Anything else is the prompt's job."""
    text = answer.strip()
    m = _FENCE.match(text)
    return m.group(1).strip() if m else text


def evaluate_profile(prompt, profile_id, profile_labels, *, model=None, max_tokens=4096, reasoning_effort=None,
                     root=ROOT):
    """Rewrite, search and score one profile. Errors give score 0 and are reported, never raised."""
    result = {"id": profile_id, "score": 0.0, "points": 0, "query": None, "top_ids": [], "error": None}
    t = time.time()
    try:
        answer = llm.complete(render(prompt, load_profile(profile_id, root)), model=model, max_tokens=max_tokens,
                              reasoning_effort=reasoning_effort)
        result["query"] = extract_query(answer)
        if not result["query"]:
            result["error"] = "empty query"
        else:
            result["top_ids"] = osr.search_boolean(result["query"])
            result["points"] = sum(profile_labels.get(cv_id, 0) for cv_id in result["top_ids"][:labels.TOP_K])
            result["score"] = labels.score(result["top_ids"], profile_labels)
    except llm.LLMError as e:
        result["error"] = f"LLM error: {e}"
    except osr.QueryError as e:
        result["error"] = f"query syntax error: {e}"
    result["seconds"] = round(time.time() - t, 2)
    return result


def evaluate_prompt(prompt, split="dev", *, workers=8, limit=None, model=None, max_tokens=4096,
                    reasoning_effort=None, root=ROOT):
    """Score a rewriting prompt on a split.

    Returns a JSON-serialisable dict; `combined_score` (0..1, mean over the
    profiles) is the number openevolve and the leaderboard rank by. Raises
    PromptError for an unusable prompt; per-profile failures only cost points."""
    check_prompt(prompt)
    ids, qrels = load_split(split, root)
    if limit:
        ids = ids[:limit]
    t = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        per_profile = list(pool.map(
            lambda qid: evaluate_profile(prompt, qid, qrels[qid], model=model, max_tokens=max_tokens,
                                         reasoning_effort=reasoning_effort, root=root),
            ids))
    queries = [p["query"] for p in per_profile if p["query"]]
    return {
        "combined_score": round(statistics.mean(p["score"] for p in per_profile), 4),
        "split": split,
        "n_profiles": len(per_profile),
        "n_errors": sum(1 for p in per_profile if p["error"]),
        "n_zero": sum(1 for p in per_profile if p["score"] == 0),
        "avg_query_chars": round(statistics.mean(len(q) for q in queries), 1) if queries else 0.0,
        "model": model or llm.settings()["model"],
        "seconds": round(time.time() - t, 1),
        "per_profile": per_profile,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Score a rewriting prompt on one split.")
    ap.add_argument("prompt_file")
    ap.add_argument("--split", default="dev", choices=SPLITS)
    ap.add_argument("--limit", type=int, help="only the first N profiles of the split")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--details", action="store_true", help="include per-profile results in the output")
    args = ap.parse_args(argv)
    with open(args.prompt_file, encoding="utf-8") as f:
        prompt = f.read()
    try:
        result = evaluate_prompt(prompt, args.split, workers=args.workers, limit=args.limit)
    except PromptError as e:
        sys.exit(f"invalid prompt: {e}")
    if not args.details:
        result.pop("per_profile")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
