# tjf-evolve: evolving LLM query-rewriting prompts (instructor repo)

Workshop demo: an LLM rewrites consultant search profiles into boolean
OpenSearch queries over 1000 CVs, and [openevolve](https://github.com/algorithmicsuperintelligence/openevolve)
evolves the rewriting prompt. Participants edit the meta-prompt and the GA
parameters and compare results on a central leaderboard.

**This is the instructor repo. Never hand it out:** it contains the heldout
profiles and labels. Participants get a package built with
`scripts/package_participant.py` (see below).

- `PLAN.md` – design, decisions, measured results, open points
- `participant_instructions.md` – setup, commands and exercise sheet for participants

## Quick start

Requirements: Docker with Compose, [uv](https://docs.astral.sh/uv/), a key for
the b.telligent chat gateway.

```bash
read -rs BTELLIGENT_API_KEY && export BTELLIGENT_API_KEY
docker compose up -d --wait          # OpenSearch on 127.0.0.1:9200
uv run evolve-eval index             # load the 1000 CVs
uv run evolve-eval check             # OpenSearch, index, LLM: expect "ok": true
uv run evolve-eval baseline          # baseline prompt on dev (about 9%)
```

Stop OpenSearch with `docker compose down` (`-v` also deletes the index).

## Common tasks

| Task | Command |
|---|---|
| Score a prompt | `uv run evolve-eval run PROMPT.txt [--split dev\|validation] [--details]` |
| Score on heldout (instructor only) | `uv run python -m evolve_demo.evaluate PROMPT.txt --split heldout` |
| Evolve | `uv run openevolve-run evolve/initial_prompt.txt evolve/evaluator.py --config evolve/configs/evolve.yaml --output evolve/runs/NAME --iterations 20` |
| Sanity check (no LLM) | `uv run python scripts/oracle_check.py` |
| Run the leaderboard (workshop) | `docker compose -f docker-compose.yml -f docker-compose.server.yml up -d --build --wait`, see [deploy/README.md](deploy/README.md) |
| Run the leaderboard (development) | `LEADERBOARD_TOKEN=... uv run --extra server evolve-leaderboard` |
| Build the participant package | `uv run python scripts/package_participant.py ../tjf-evolve-participant --zip --git` |
| Tests | `uv run --extra server python -m unittest discover tests` |

Notes:
- `evolve-eval` prints one JSON object per command; exit code 0 ok, 1 invalid
  input, 2 setup problem.
- 20 evolution iterations take about 7 minutes (about 840 rewriter calls). The
  default setup reaches about 30% on dev after 5–8 iterations and then levels
  off; details in `PLAN.md` section 8.
- On the leaderboard server always use `uv run --extra server …`; a plain
  `uv run` syncs the environment without FastAPI and uvicorn.
- The leaderboard needs OpenSearch with the index, the `heldout/` folder and
  its own API key, and enters the baseline automatically on first start. For
  the workshop it runs in Docker on the instructor laptop (submissions in a
  Docker volume); making it reachable from other machines under WSL2 needs
  Windows-side settings, see [deploy/README.md](deploy/README.md).

## Regenerating the data

Only needed if the data itself should change. The order matters:

```bash
python3 query_generation.py              # 100 profiles into queries/ (clears the folder)
python3 CV_generation.py                 # 1000 CVs into CVs/, planted against the profiles
uv run python scripts/make_qrels.py      # labels and dev/validation/heldout split
uv run evolve-eval index                 # reload OpenSearch
uv run python scripts/oracle_check.py    # check the task is neither trivial nor impossible
```

The generators and the split are seeded; `make_qrels.py` is verified to
reproduce its files exactly, the generators are not (check with `git diff`).
After a data change, all scores in `PLAN.md` are outdated, and a running
leaderboard must be restarted with a fresh database.

## Layout

```
CVs/ queries/                 1000 CVs, 100 search profiles (incl. 40 heldout profiles!)
data/                         dev + validation split and labels (shipped to participants)
heldout/heldout.json          heldout ids and labels (server only, never shipped)
src/evolve_demo/              labels, OpenSearch, LLM client, core evaluation, CLI, leaderboard
evolve/initial_prompt.txt     deliberately weak baseline rewriting prompt (keep it weak)
evolve/evaluator.py           openevolve wrapper: metrics + feedback for the evolution model
evolve/configs/evolve.yaml    GA parameters
evolve/meta/templates/        meta-prompt (system message, rewrite request)
evolve/runs/                  openevolve output (gitignored)
docker-compose.server.yml     indexer + leaderboard services (instructor only)
deploy/                       leaderboard Dockerfile and deployment runbook
instructor/                   reference solutions (e.g. meta-prompt with hints for exercise 2)
scripts/                      make_qrels, oracle_check, package_participant (instructor only)
query_generation.py CV_generation.py   data generators (instructor only)
tests/                        unit tests
```

## Configuration (environment variables)

| Variable | Purpose |
|---|---|
| `BTELLIGENT_API_KEY` | key for the default LLM provider (gateway, model `gpt-6-luna`) |
| `LLM_PROVIDER` | `btelligent` (default), `gemini` or `openrouter`, with `GEMINI_API_KEY` / `OPENROUTER_API_KEY` |
| `LLM_API_KEY`, `LLM_API_BASE`, `REWRITER_MODEL` | override key, endpoint and rewriter model |
| `LLM_CACHE_DIR` | cache LLM answers on disk (identical repeated evaluations) |
| `OPENSEARCH_URL`, `OPENSEARCH_INDEX` | default `http://localhost:9200`, `cvs` |
| `EVOLVE_EVAL_LIMIT` | evaluate only the first N dev profiles in openevolve (cheap test runs) |
| `LEADERBOARD_TOKEN`, `LEADERBOARD_DB` | server: shared workshop token, database file |
| `LEADERBOARD_URL` | client: leaderboard address for `evolve-eval submit` (plus `LEADERBOARD_TOKEN`) |

Keys belong in the environment, not in files. A `.env` file (see `.env.example`)
also works and is gitignored, but real environment variables take precedence.
