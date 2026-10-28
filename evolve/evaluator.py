"""openevolve evaluator: scores a candidate rewriting prompt on the dev split.

openevolve writes each candidate prompt to a temporary .txt file and calls
evaluate(path). The scoring itself is the core evaluate_prompt() that the CLI
and the leaderboard use as well; this file only adapts it to openevolve:

- metrics (numbers only): combined_score (fitness, 0..1), counts, and the two
  MAP-Elites feature dimensions prompt_length and avg_query_chars
- artifacts (text): feedback for the evolution LLM, i.e. what went wrong on
  which profiles; it appears in the {artifacts} section of the meta-prompt

EVOLVE_EVAL_LIMIT=N scores only the first N dev profiles (cheap smoke tests).
"""
import os

from openevolve.evaluation_result import EvaluationResult

from evolve_demo import evaluate as core
from evolve_demo import labels

SPLIT = "dev"
N_FAILURES_SHOWN = 4   # worst profiles shown to the evolution LLM
N_SUCCESSES_SHOWN = 2  # best profiles shown to the evolution LLM


def _profile_summary(profile_id):
    q = labels.parse_query(core.load_profile(profile_id))
    parts = [f"must-have: {', '.join(q['must'])}"]
    if q["nice"]:
        parts.append(f"nice-to-have: {', '.join(q['nice'])}")
    if q["certs"]:
        parts.append(f"certifications: {', '.join(q['certs'])}")
    parts.append(f"min. {q['min_years']} years")
    return "; ".join(parts)


def _example(p):
    lines = [f"{p['id']}: {p['points']} of {labels.MAX_SCORE} points, {len(p['top_ids'])} hits",
             f"  profile: {_profile_summary(p['id'])}",
             f"  generated query: {p['query'] or '(none)'}"]
    if p["error"]:
        lines.append(f"  error: {p['error']}")
    return "\n".join(lines)


def feedback(result):
    """Readable feedback text for the evolution LLM."""
    per = result["per_profile"]
    no_hits = sum(1 for p in per if not p["error"] and not p["top_ids"])
    lines = [f"Score {result['combined_score']:.1%} on {result['n_profiles']} search profiles "
             f"(points of the top {labels.TOP_K} CVs / {labels.MAX_SCORE}; very good fit = 2, reasonable fit = 1).",
             f"{result['n_zero']} profiles scored 0 points; {no_hits} queries returned no CVs at all; "
             f"{result['n_errors']} failed (syntax or LLM errors)."]
    ranked = sorted(per, key=lambda p: (p["score"], p["id"]))
    lines += ["", "Worst profiles:"] + [_example(p) for p in ranked[:N_FAILURES_SHOWN]]
    best = [p for p in reversed(ranked) if p["score"] > 0][:N_SUCCESSES_SHOWN]
    if best:
        lines += ["", "Best profiles:"] + [_example(p) for p in best]
    return "\n".join(lines)


def evaluate(program_path):
    with open(program_path, encoding="utf-8") as f:
        prompt = f.read()
    metrics = {"combined_score": 0.0, "n_zero": 0, "n_errors": 0,
               "prompt_length": len(prompt), "avg_query_chars": 0.0}
    try:
        result = core.evaluate_prompt(prompt, SPLIT, limit=int(os.environ.get("EVOLVE_EVAL_LIMIT", 0)) or None)
    except core.PromptError as e:
        return EvaluationResult(metrics=metrics, artifacts={"feedback": f"Invalid prompt, score 0: {e}"})
    metrics.update({k: result[k] for k in ("combined_score", "n_zero", "n_errors", "avg_query_chars")})
    return EvaluationResult(metrics=metrics, artifacts={"feedback": feedback(result)})
