# MinecraftAsia — Server Rankings

A live ranking board for Asia Minecraft servers, scored on **players online**,
**24h daily peak**, **24h uptime**, and **ping**. Fully static frontend —
deployable straight to GitHub Pages, no server required to *serve* the site.

## Why this isn't a single "run app.py" project

GitHub Pages only serves static files (HTML/CSS/JS/JSON) — it cannot run
Flask, SQLite, or a background thread. And GitHub Actions' scheduled jobs
have a 5-minute floor and can slip further under load, so they can't give you
honest 1-minute samples either.

So the pieces are split by what each part is actually good at:

| Piece | Runs where | Job |
|---|---|---|
| `scripts/poller.py` | Anywhere always-on that **you** control (your PC, a Pi, a free Oracle Cloud VM, a small always-on Fly.io/Render worker) | Samples all servers every **60 seconds** (real per-minute data), writes `data/live.json` + `data/history/<server>/raw.json`, pushes to git every ~5 minutes |
| `.github/workflows/aggregate.yml` + `scripts/aggregate.py` | GitHub Actions (free, scheduled) | Rolls raw minute samples into hourly/daily buckets, prunes old data, commits the result |
| `index.html` / `css/` / `js/` | GitHub Pages (free, static) | Reads the committed JSON and renders the board — no backend calls at all |

Net result: it's 100% free, lives entirely in one GitHub repo, and you get
true minute-level graphs for short ranges without needing a paid server for
the *website* — only a small always-on box for the *poller*.

## Data ranges

| UI range | Backed by | File |
|---|---|---|
| 5m / 10m / 30m / 1h / 24h | raw minute samples (3-day rolling window) | `data/history/<server>/raw.json` |
| 7d | hourly rollups (90-day window) | `data/history/<server>/hourly.json` |
| 1mo / 1y | daily rollups (~13-month window) | `data/history/<server>/daily.json` |

## Ranking formula

```
overall = 30% × players-online-score
        + 25% × 24h-daily-peak-score
        + 25% × 24h-uptime-%
        + 20% × ping-score
```
Weights live in `scripts/common.py` (`W_ONLINE`, `W_DAILY`, `W_UPTIME`,
`W_PING`) — change them there; the frontend reads whatever weights `live.json`
reports so the "RANK BY" note stays in sync automatically. You can also
re-sort the board client-side by any single metric using the buttons in the
toolbar (Overall / Online / Daily peak / Uptime / Ping).

## Setup

### 1. Push this repo to GitHub, enable Pages

Settings → Pages → deploy from the `main` branch, root folder. Your site will
be live at `https://<you>.github.io/<repo>/`.

### 2. Run the poller somewhere always-on

```bash
git clone https://github.com/<you>/<repo>.git
cd <repo>
python -m pip install -r requirements.txt
python scripts/poller.py
```

Make sure `git push` works from that machine without an interactive prompt
(an SSH deploy key with write access, or a stored HTTPS PAT). Run it under
`systemd`, `pm2`, or inside `tmux`/`screen` so it survives reboots/logouts.

A cheap way to get a permanently-free always-on box for this: Oracle Cloud's
Always Free tier VM, a spare Raspberry Pi, or a small free-tier worker on
Fly.io/Render.

### 3. Aggregation runs itself

`.github/workflows/aggregate.yml` is already scheduled for every 30 minutes
and needs no setup beyond the repo being on GitHub with Actions enabled
(Settings → Actions → General → allow workflows to have write permissions).

### 4. Add or remove servers

Edit the `SERVERS` list in `scripts/common.py`. New servers automatically get
their own `data/history/<server>/` folder on the poller's next run.

## Font

Server names, MOTDs, and numeric stats use **Monocraft**
(https://github.com/IdreesInc/Monocraft), a free MIT-licensed pixel font
inspired by Minecraft's own typeface, loaded from jsDelivr in `css/style.css`
— no download or build step needed. (Mojang's actual "Minecraftia"/"Mojangles"
typefaces aren't freely licensed for redistribution, so this is the safe,
legal stand-in that looks the part.)

## Local preview

Because the page `fetch()`s local JSON files, opening `index.html` directly
(`file://`) will fail on CORS. Serve it locally instead:

```bash
python -m http.server 8000
# open http://localhost:8000
```
