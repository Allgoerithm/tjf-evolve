# Participant instructions

(Work in progress. More sections will follow.)

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

## Scoring a rewriting prompt

```bash
uv run evolve-eval baseline                       # the starting prompt, dev split
uv run evolve-eval run my_prompt.txt              # your own prompt, dev split
uv run evolve-eval run my_prompt.txt --split validation --details
```

A rewriting prompt must contain the placeholder `{profile}`; the search
profile is inserted there. `--details` shows the generated query and the
result for every profile.
