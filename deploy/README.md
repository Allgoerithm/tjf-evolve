# Leaderboard deployment (instructor laptop)

The leaderboard runs on the instructor laptop with Docker Compose, next to the
OpenSearch container. Participants reach it over the workshop network at
`http://<laptop-ip>:8000`.

Running on the laptop is the current decision but may be reconsidered (see
open point 4 in `PLAN.md`): the compose setup is host-independent and also
works on a VM or an internal server that all participants can reach.

Files:
- `../docker-compose.server.yml` – adds the `indexer` (one-shot, skips if the
  index is complete) and `leaderboard` services to `../docker-compose.yml`.
- `leaderboard.Dockerfile` – image with the Python dependencies only (413 MB).
  Code and data, including `heldout/`, are mounted read-only from the repo.
- `../.dockerignore` – keeps the build context to `pyproject.toml` and `uv.lock`.

None of these files are part of the participant package.

## Start

```bash
cd ~/repos/tjf-evolve
read -rs BTELLIGENT_API_KEY && export BTELLIGENT_API_KEY   # the server's own LLM key
read -rs LEADERBOARD_TOKEN && export LEADERBOARD_TOKEN     # workshop token, handed out to participants
docker compose -f docker-compose.yml -f docker-compose.server.yml up -d --build --wait
```

Compose refuses to start the leaderboard if either variable is missing. The
key and token are passed from the shell environment and never written to a
file. Optional: `LEADERBOARD_PORT` (default 8000), `LLM_PROVIDER`.

Check: `curl -s localhost:8000/api/submissions` lists the baseline, which is
entered and scored automatically on the first start (about a minute). Then
open `http://localhost:8000/` in the Windows browser.

## Operate

```bash
F="-f docker-compose.yml -f docker-compose.server.yml"
docker compose $F logs -f leaderboard        # follow the server log
docker compose $F restart leaderboard        # queued submissions are re-queued
docker compose $F stop leaderboard           # stop the server, keep the data
docker compose $F down                       # stop everything, keep index and submissions
```

Code changes in `src/` take effect after `restart` (the code is mounted, not
copied). Rebuild (`up -d --build`) only after dependency changes.

Submissions are stored in the Docker volume `tjf-evolve_leaderboard-data`.
- Back up: `docker cp tjf-leaderboard:/data/leaderboard.sqlite3 ./leaderboard-backup.sqlite3`
- Fresh start for a new workshop: `docker compose $F rm -sf leaderboard` and
  `docker volume rm tjf-evolve_leaderboard-data` (deletes all submissions).
  `docker compose $F down -v` also deletes the OpenSearch index.

## Make it reachable from other machines (WSL2)

Docker runs inside WSL2. In WSL2's default NAT networking mode, published
ports are reachable from Windows itself (`localhost:8000`) but **not** from
other machines. One of the following is needed, in an **administrator**
PowerShell on Windows. This was not tested yet: do a test with a second
machine on the actual workshop network beforehand.

**Option A – mirrored networking (Windows 11 22H2 or later, recommended).**
WSL then shares the Windows network interfaces and IP address.

1. Add to `%UserProfile%\.wslconfig`:
   ```ini
   [wsl2]
   networkingMode=mirrored
   ```
2. `wsl --shutdown`, then reopen WSL and start the stack again.
3. Allow inbound connections on port 8000:
   ```powershell
   New-NetFirewallRule -DisplayName "tjf leaderboard" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
   Set-NetFirewallHyperVVMSetting -Name '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -DefaultInboundAction Allow
   ```
   The second command opens the Hyper-V firewall for WSL, which filters
   inbound traffic in mirrored mode.

**Option B – port proxy (any Windows version, NAT mode).**

```powershell
$wslIp = (wsl hostname -I).Trim().Split(" ")[0]
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8000 connectaddress=$wslIp connectport=8000
New-NetFirewallRule -DisplayName "tjf leaderboard" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

The WSL IP changes after a reboot or `wsl --shutdown`; then delete and re-add
the proxy (`netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=8000`).

**Then:** find the laptop's address on the workshop network with `ipconfig`
(Windows) and give participants `LEADERBOARD_URL=http://<that address>:8000`
plus the token. Guest Wi-Fi networks often block traffic between devices
("client isolation"); if a second machine cannot connect, use a network
without isolation or a phone hotspot.

**After the workshop:** remove the firewall rule
(`Remove-NetFirewallRule -DisplayName "tjf leaderboard"`) and, for option B,
the port proxy.

## Security

- Only the leaderboard port is exposed. OpenSearch stays bound to
  `127.0.0.1:9200` (security plugin disabled, never expose it).
- Plain HTTP and a shared token: anyone on the network who has the token can
  submit under any name; the token travels unencrypted. Acceptable for a
  workshop network, not for the internet.
- The API returns scores only; heldout profiles, generated queries and
  per-profile results stay on the laptop.
- Every submission costs about 60 LLM calls on the server's key; the server
  allows one pending submission per participant and one submission every two
  minutes.

## Tested

On the instructor laptop (WSL2, Docker 29.9, NAT mode), from inside WSL:
stack up in 10 s (image already built), indexer skipped the complete index,
a real submission through the container's WSL address scored (heldout 28.0%,
validation 37.0% for the 20-iteration best prompt; baseline 6.5% / 4.0%),
submissions survived a container restart, the repo mount is read-only.
**Not tested:** access from another machine (needs option A or B).
