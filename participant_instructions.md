# Participant instructions

In this workshop an LLM turns staffing requests ("search profiles") into
boolean search queries for a CV search on OpenSearch. How well that works
depends on the **rewriting prompt** the LLM gets. Instead of tuning that prompt
by hand, you let [openevolve](https://github.com/algorithmicsuperintelligence/openevolve)
evolve it: an evolution model writes new candidate prompts, each candidate is
scored on 40 search profiles, and the best ones become parents of the next
candidates. You steer the evolution through the **meta-prompt** (what the
evolution model is told) and the **GA parameters** (how the search runs), and
compare your results on a shared leaderboard.

Work through the sections in order: API key, setup, then the exercises at the
end. The sections in between are the reference for the commands.

## Setting your API key

The workshop code talks to the b.telligent chat gateway (OpenAI-compatible). It reads the key from the
environment variable `BTELLIGENT_API_KEY`. You do **not** need to create a `.env`
file, so the key never has to be written to disk.

### Set the key for the current shell session

```bash
read -rs BTELLIGENT_API_KEY && export BTELLIGENT_API_KEY
```

Paste the key and press Enter. The key stays in the memory of that shell only.
The `-s` flag keeps it from being echoed in the terminal.

Run all workshop commands from the same terminal. A new terminal needs the
command again.

### Do not do this

```bash
export BTELLIGENT_API_KEY=sk-...   # ends up in ~/.bash_history
```

Typing the key directly into the command line stores it in your shell history.

### Notes

- If you start an editor or a coding agent (e.g. Claude Code) from the same
  terminal, it inherits the variable. Export the key first, then start the tool.
- Never commit the key. The optional `.env` file is gitignored, but the
  environment variable is the safer choice.
- If both exist, the environment variable takes precedence over `.env`.

## Setup

Requirements: Docker (with Compose) and [uv](https://docs.astral.sh/uv/).

```bash
docker compose up -d --wait     # start OpenSearch (first start downloads ~1 GB)
uv run evolve-eval index        # load the 1000 CVs into OpenSearch
uv run evolve-eval check        # checks OpenSearch, the index and your API key
```

`check` prints `"ok": true` when everything works. Every `evolve-eval` command
prints one JSON object; on problems it contains an `"error"` with a hint.

If Docker says "permission denied" right after you were added to the `docker`
group, log out and in again (group membership applies only to new logins).

## How the score works

For every search profile, the rewriting prompt (with the profile inserted at
`{profile}`) goes to the LLM, the answer runs as a query against the 1000 CVs,
and the top 5 CVs are scored: 2 points for a very good fit, 1 point for a
reasonable fit, 0 otherwise. The score is the points divided by 10, averaged
over the profiles. A query with a syntax error or without any hits scores 0.

Not every profile has five well-fitting CVs, so even a perfect prompt stays
well below 100%: about 68% is the best reachable score.

The profiles come in three splits:
- **dev** (40 profiles): used by the evolution and by default in `evolve-eval`.
- **validation** (20 profiles): for your own check whether a prompt also works
  on profiles the evolution has not seen.
- **heldout** (40 profiles): hidden, only on the leaderboard server. Your
  leaderboard rank is based on these.

## Scoring a rewriting prompt

```bash
uv run evolve-eval baseline                       # the starting prompt, dev split
uv run evolve-eval run my_prompt.txt              # your own prompt, dev split
uv run evolve-eval run my_prompt.txt --split validation --details
```

A rewriting prompt must contain the placeholder `{profile}`; the search
profile is inserted there. `--details` shows the generated query and the
result for every profile.

## Evolving the rewriting prompt

```bash
uv run openevolve-run evolve/initial_prompt.txt evolve/evaluator.py \
    --config evolve/configs/evolve.yaml --output evolve/runs/my-run --iterations 5
```

Five iterations take about 3 minutes. The best prompt ends up in
`evolve/runs/my-run/best/best_program.txt`. Check whether it also works on
profiles the evolution has not seen:

```bash
uv run evolve-eval run evolve/runs/my-run/best/best_program.txt --split validation
```

What you can change:
- **Meta-prompt** (`evolve/meta/templates/`): `system_message.txt` tells the
  evolution model what the system does and what to aim for;
  `full_rewrite_user.txt` is the request it gets for every new candidate. In
  that file, literal braces must be doubled (`{{profile}}`).
- **GA parameters** (`evolve/configs/evolve.yaml`): iterations, islands,
  population, exploration/exploitation, feature dimensions, temperature. The
  comments in the file explain each setting.

## Submitting to the leaderboard

You get the leaderboard address and the workshop token from the instructor.

```bash
export LEADERBOARD_URL=http://<address>:8000
read -rs LEADERBOARD_TOKEN && export LEADERBOARD_TOKEN
uv run evolve-eval submit evolve/runs/my-run/best/best_program.txt --name "Your Name" --wait
```

The submission contains your rewriting prompt plus your current meta-prompt
(`evolve/meta/templates/`) and GA config (`evolve/configs/evolve.yaml`), so
others can see how you got there. The server scores the prompt on hidden
profiles that you never see; this takes about a minute. You can submit again
once the previous submission is scored and two minutes have passed.

## Exercises

Tips for all exercises:
- Use a new `--output` folder for every run (`evolve/runs/ex1`, `evolve/runs/ex2-hints`, …)
  so you can compare runs later. Each folder keeps all candidate prompts with
  their scores and feedback in `checkpoints/`.
- Change one thing at a time; otherwise you cannot tell what helped.
- Scores vary by a point or two between identical runs, because the LLM does
  not answer the same way every time. Do not read too much into small differences.
- The meta-prompt and GA config are part of your submission. Commit or copy a
  version you want to keep before you change it again.

### Exercise 0: Look at the starting point

1. Score the starting prompt with details:
   `uv run evolve-eval baseline --details > baseline.json`
2. Read `evolve/initial_prompt.txt` and a few generated queries in
   `baseline.json`. How many profiles score 0, and why? Compare a query with
   its profile in `queries/<id>.txt` and with a few CVs in `CVs/`.
3. Optional: write your own improved prompt into a file and score it with
   `uv run evolve-eval run my_prompt.txt`. Keep the score in mind for later.

### Exercise 1: Evolve with the defaults

1. Run 5 iterations with the default meta-prompt and GA config
   (`--output evolve/runs/ex1`, about 3 minutes).
2. Read `evolve/runs/ex1/best/best_program.txt`. What did the evolution change
   compared with the starting prompt? Is it what you would have done by hand?
3. Score the best prompt on validation. Is the score close to the dev score?
4. Submit it to the leaderboard so you have a first entry.

### Exercise 2: Improve the meta-prompt

The evolution model only knows what `evolve/meta/templates/system_message.txt`
and `full_rewrite_user.txt` tell it, plus the feedback on its candidates.
Think about what it does **not** know:
- What does a CV document in the index look like, which fields does it have,
  and which query syntax does OpenSearch accept? (See `CVs/` and
  `src/evolve_demo/opensearch.py`.)
- When exactly does a CV count as a very good or a reasonable fit? (See
  `src/evolve_demo/labels.py`.)
- Which parts of a search profile matter for the score, and which do not?

Add what you think helps to the meta-prompt, run again with a new output
folder (5–10 iterations), and compare with exercise 1 on dev and validation.
Remember that `full_rewrite_user.txt` is filled in with Python's
`str.format`: literal braces must be doubled there (`{{profile}}`), not in
`system_message.txt`.

### Exercise 3: Tune the GA parameters

Pick one or two settings in `evolve/configs/evolve.yaml`, form an expectation
first, then run and compare. Ideas:
- `max_iterations` / `--iterations`: does the score keep rising after 10
  iterations, or does it level off?
- `num_islands`, `migration_interval`: more separate populations, more variety?
- `exploration_ratio` / `exploitation_ratio`: build on the best prompts, or try
  more different ones?
- `llm.temperature`: bolder or more careful rewrites of the prompt?
- `num_top_programs`, `num_diverse_programs`: how many earlier prompts the
  evolution model sees as examples.
- `include_artifacts: false`: what happens if the evolution model no longer
  sees the feedback on failing profiles?
- `feature_dimensions`: which properties of a prompt should count as
  "different" for the diversity archive?

Every candidate costs 40 LLM calls, so 20 iterations are about 840 calls and
take roughly 7 minutes.

### Exercise 4: Compare on the leaderboard

Submit your best prompt (`evolve-eval submit … --wait`). Compare dev,
validation and heldout scores: where do they diverge, and why? On the
leaderboard, open the entries of others to see their meta-prompts and
GA configs.

Questions for the final discussion:
- Which change made the biggest difference: meta-prompt, GA parameters, or
  simply more iterations?
- What did the evolution find that you would not have tried by hand, and what
  did it never find on its own?
- How much does a score on 40 profiles tell you? What would you need before
  using such a prompt in production?
