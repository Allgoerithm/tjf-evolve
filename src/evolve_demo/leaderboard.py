"""Central leaderboard server (FastAPI + SQLite), run by the instructor.

Participants submit a bundle (name, rewriting prompt, meta-prompt templates,
GA config) with `evolve-eval submit`. The server scores the rewriting prompt
on the heldout split (ranking) and on validation (reference) with the same
core evaluate_prompt() and shows a ranked table. Heldout profiles, labels and
per-profile results never leave the server; participants only see scores.

Submissions are scored one at a time by a single background worker, so the
load on OpenSearch and the LLM gateway stays predictable.

  uv run --extra server evolve-leaderboard [--host 0.0.0.0] [--port 8000]

Environment: LEADERBOARD_TOKEN (shared workshop token, required),
LEADERBOARD_DB (default leaderboard.sqlite3), plus the usual LLM and
OpenSearch settings (the server uses its own API key).
"""
import argparse
import datetime
import html
import json
import os
import queue
import secrets
import sqlite3
import threading
import time

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import evaluate

DB_PATH = os.environ.get("LEADERBOARD_DB", os.path.join(evaluate.ROOT, "leaderboard.sqlite3"))
BASELINE_NAME = "baseline"
MAX_META_CHARS = 50_000      # all meta-prompt templates together
MAX_CONFIG_CHARS = 20_000
MIN_SECONDS_BETWEEN = 120    # per participant
SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    participant TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    rewriting_prompt TEXT NOT NULL,
    meta_prompt TEXT NOT NULL,          -- JSON {file name: text}
    ga_config TEXT NOT NULL,
    status TEXT NOT NULL,               -- queued | evaluating | done | failed
    heldout_score REAL,
    validation_score REAL,
    heldout_zero INTEGER,
    error TEXT
)"""


class Submission(BaseModel):
    participant: str = Field(min_length=1, max_length=40)
    rewriting_prompt: str = Field(min_length=1, max_length=evaluate.MAX_PROMPT_CHARS)
    meta_prompt: dict[str, str] = Field(default_factory=dict)
    ga_config: str = Field(default="", max_length=MAX_CONFIG_CHARS)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def connect():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


class Store:
    """SQLite access, serialised by one lock (the load is tiny)."""

    def __init__(self):
        self.con = connect()
        self.lock = threading.Lock()
        with self.lock:
            self.con.execute(SCHEMA)
            self.con.commit()

    def query(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.con.execute(sql, args).fetchall()]

    def execute(self, sql, args=()):
        with self.lock:
            cur = self.con.execute(sql, args)
            self.con.commit()
            return cur.lastrowid


class Scorer:
    """Background worker: scores queued submissions one at a time."""

    def __init__(self, store, evaluate_fn=evaluate.evaluate_prompt):
        self.store = store
        self.evaluate_fn = evaluate_fn
        self.jobs = queue.Queue()

    def start(self):
        # Re-queue work that was interrupted by a restart.
        for row in self.store.query("SELECT id FROM submissions WHERE status IN ('queued', 'evaluating') ORDER BY id"):
            self.store.execute("UPDATE submissions SET status = 'queued' WHERE id = ?", (row["id"],))
            self.jobs.put(row["id"])
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        while True:
            self.score(self.jobs.get())

    def score(self, sid):
        prompt = self.store.query("SELECT rewriting_prompt FROM submissions WHERE id = ?", (sid,))[0]["rewriting_prompt"]
        self.store.execute("UPDATE submissions SET status = 'evaluating' WHERE id = ?", (sid,))
        try:
            heldout = self.evaluate_fn(prompt, "heldout")
            validation = self.evaluate_fn(prompt, "validation")
            if heldout["n_errors"] == heldout["n_profiles"]:
                raise RuntimeError("every profile failed: " + str(heldout["per_profile"][0]["error"]))
        except Exception as e:   # noqa: BLE001 – any failure is shown in the table
            self.store.execute("UPDATE submissions SET status = 'failed', error = ? WHERE id = ?",
                               (f"{type(e).__name__}: {e}"[:500], sid))
            return
        self.store.execute(
            "UPDATE submissions SET status = 'done', heldout_score = ?, validation_score = ?, heldout_zero = ?,"
            " error = NULL WHERE id = ?",
            (heldout["combined_score"], validation["combined_score"], heldout["n_zero"], sid))


def create_app(token=None, store=None, scorer=None, baseline_file=None):
    token = token or os.environ.get("LEADERBOARD_TOKEN")
    if not token:
        raise SystemExit("set LEADERBOARD_TOKEN (shared workshop token)")
    store = store or Store()
    scorer = scorer or Scorer(store)
    baseline_file = baseline_file or os.path.join(evaluate.ROOT, "evolve", "initial_prompt.txt")
    app = FastAPI(title="tjf-evolve leaderboard")

    def check_token(authorization):
        if not authorization or not secrets.compare_digest(authorization, f"Bearer {token}"):
            raise HTTPException(401, "missing or wrong workshop token")

    def add(sub):
        return store.execute(
            "INSERT INTO submissions (participant, submitted_at, rewriting_prompt, meta_prompt, ga_config, status)"
            " VALUES (?, ?, ?, ?, ?, 'queued')",
            (sub.participant, now(), sub.rewriting_prompt, json.dumps(sub.meta_prompt), sub.ga_config))

    # The baseline is a fixed row, submitted once.
    if not store.query("SELECT id FROM submissions WHERE participant = ?", (BASELINE_NAME,)):
        with open(baseline_file, encoding="utf-8") as f:
            add(Submission(participant=BASELINE_NAME, rewriting_prompt=f.read()))
    scorer.start()

    @app.post("/submit")
    def submit(sub: Submission, authorization: str | None = Header(default=None)):
        check_token(authorization)
        name = sub.participant.strip()
        if name.lower() == BASELINE_NAME:
            raise HTTPException(400, f"'{BASELINE_NAME}' is reserved")
        sub.participant = name
        try:
            evaluate.check_prompt(sub.rewriting_prompt)
        except evaluate.PromptError as e:
            raise HTTPException(400, str(e))
        if sum(len(k) + len(v) for k, v in sub.meta_prompt.items()) > MAX_META_CHARS:
            raise HTTPException(400, f"meta-prompt templates exceed {MAX_META_CHARS} characters")
        mine = store.query("SELECT submitted_at, status FROM submissions WHERE participant = ? ORDER BY id DESC",
                           (name,))
        if any(r["status"] in ("queued", "evaluating") for r in mine):
            raise HTTPException(429, "your previous submission is still being scored")
        if mine:
            age = time.time() - datetime.datetime.fromisoformat(mine[0]["submitted_at"]).timestamp()
            if age < MIN_SECONDS_BETWEEN:
                raise HTTPException(429, f"please wait {int(MIN_SECONDS_BETWEEN - age)} s before submitting again")
        sid = add(sub)
        scorer.jobs.put(sid)
        return {"id": sid, "status": "queued", "position": scorer.jobs.qsize()}

    @app.get("/api/submissions")
    def submissions():
        return ranked(store)

    @app.get("/api/submissions/{sid}")
    def submission(sid: int):
        rows = store.query(f"SELECT {PUBLIC_COLUMNS} FROM submissions WHERE id = ?", (sid,))
        if not rows:
            raise HTTPException(404, "no such submission")
        return rows[0]

    @app.get("/", response_class=HTMLResponse)
    def table():
        return render_table(ranked(store))

    @app.get("/submission/{sid}", response_class=HTMLResponse)
    def detail(sid: int):
        rows = store.query("SELECT * FROM submissions WHERE id = ?", (sid,))
        if not rows:
            raise HTTPException(404, "no such submission")
        return render_detail(rows[0])

    app.state.store, app.state.scorer = store, scorer
    return app


PUBLIC_COLUMNS = ("id, participant, submitted_at, status, heldout_score, validation_score, heldout_zero, error")


def ranked(store):
    """Scored submissions by heldout score (earlier wins ties), then pending and failed ones."""
    return store.query(
        f"SELECT {PUBLIC_COLUMNS} FROM submissions ORDER BY status != 'done', heldout_score DESC, id")


STYLE = """
:root { --bg: #ffffff; --fg: #1d1d1f; --muted: #6e6e73; --line: #e5e5ea; --accent: #0a84ff; --base: #f2f2f7; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #1c1c1e; --fg: #f2f2f7; --muted: #a1a1a6; --line: #38383a; --accent: #64d2ff; --base: #2c2c2e; }
}
body { background: var(--bg); color: var(--fg); font: 15px/1.5 system-ui, sans-serif; margin: 0 auto;
       max-width: 960px; padding: 24px 16px; }
h1 { font-size: 22px; } a { color: var(--accent); }
.wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; }
th, td { border-bottom: 1px solid var(--line); padding: 8px 10px; text-align: left; white-space: nowrap; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
tr.baseline td { background: var(--base); }
.muted { color: var(--muted); }
pre { background: var(--base); padding: 12px; white-space: pre-wrap; word-break: break-word; border-radius: 6px; }
"""


def page(title, body, refresh=False):
    meta = '<meta http-equiv="refresh" content="10">' if refresh else ""
    return (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width, initial-scale=1">{meta}<title>{html.escape(title)}</title>'
            f"<style>{STYLE}</style></head><body>{body}</body></html>")


def pct(x):
    return "" if x is None else f"{x:.1%}"


def render_table(rows):
    lines, rank = [], 0
    for r in rows:
        if r["status"] == "done":
            rank += 1
        status = {"done": "", "failed": "failed"}.get(r["status"], r["status"] + " …")
        cls = ' class="baseline"' if r["participant"] == BASELINE_NAME else ""
        lines.append(
            f"<tr{cls}><td class='num'>{rank if r['status'] == 'done' else ''}</td>"
            f"<td><a href='/submission/{r['id']}'>{html.escape(r['participant'])}</a></td>"
            f"<td class='num'>{pct(r['heldout_score'])}</td><td class='num'>{pct(r['validation_score'])}</td>"
            f"<td class='muted'>{html.escape(status)}</td>"
            f"<td class='muted'>{html.escape(r['submitted_at'][11:16])} UTC</td></tr>")
    body = ("<h1>Query-rewriting leaderboard</h1>"
            "<p class='muted'>Ranked by the score on the hidden heldout profiles. Validation is shown for "
            "reference. The page refreshes every 10 seconds.</p>"
            "<div class='wrap'><table><tr><th class='num'>#</th><th>Participant</th><th class='num'>Heldout</th>"
            "<th class='num'>Validation</th><th>Status</th><th>Submitted</th></tr>"
            + "".join(lines) + "</table></div>")
    return page("Leaderboard", body, refresh=True)


def render_detail(r):
    meta = json.loads(r["meta_prompt"] or "{}")
    parts = [f"<p><a href='/'>← leaderboard</a></p><h1>{html.escape(r['participant'])}</h1>",
             f"<p>Heldout {pct(r['heldout_score']) or '–'} · validation {pct(r['validation_score']) or '–'} · "
             f"{html.escape(r['status'])} · submitted {html.escape(r['submitted_at'])}</p>"]
    if r["error"]:
        parts.append(f"<p>Error: {html.escape(r['error'])}</p>")
    parts.append(f"<h2>Rewriting prompt</h2><pre>{html.escape(r['rewriting_prompt'])}</pre>")
    for name, text in sorted(meta.items()):
        parts.append(f"<h2>Meta-prompt: {html.escape(name)}</h2><pre>{html.escape(text)}</pre>")
    if r["ga_config"]:
        parts.append(f"<h2>GA config</h2><pre>{html.escape(r['ga_config'])}</pre>")
    return page(f"Submission {r['id']}", "".join(parts))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="evolve-leaderboard", description="Run the leaderboard server.")
    ap.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 to accept connections from other machines")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args(argv)
    import uvicorn
    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
