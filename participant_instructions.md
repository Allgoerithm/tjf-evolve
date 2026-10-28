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

### Check that it works

```bash
python3 scripts/llm_check.py
```

### Notes

- If you start an editor or a coding agent (e.g. Claude Code) from the same
  terminal, it inherits the variable. Export the key first, then start the tool.
- Never commit the key. The optional `.env` file is gitignored, but the
  environment variable is the safer choice.
- If both exist, the environment variable takes precedence over `.env`.
