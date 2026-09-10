# MinecraftAsia — Server Rankings

A live ranking board for Asia Minecraft servers, scored on **players online**,
**24h daily peak**, **24h uptime**, and **ping**. Fully static frontend,
fully GitHub-hosted data pipeline — no external server needed.

## How it works (GitHub-only)

GitHub Pages only serves static files — it can't run a persistent process.
GitHub Actions jobs aren't persistent either (a run executes and stops), and
scheduled runs have a 5-minute floor that can slip further under load. So
instead of one continuous poller, `.github/workflows/update.yml` runs a
**burst** every ~5 minutes:

1. `scripts/burst_poll.py` — takes 4 samples, spaced a real 60 seconds
   apart, all within that one job run. Writes `data/live.json` and appends
   to each server's `data/history/<server>/raw.json`.
2. `scripts/aggregate.py` — rolls raw samples into hourly/daily buckets and
   prunes old data.
3. The workflow commits everything in one shot.

Net effect: genuinely per-minute data *within* each burst, with a possible
small gap *between* bursts if GitHub delays the schedule (usually a few
minutes). No VM, Pi, or always-on machine required.

**Keep the repo public** — Actions minutes are unlimited and free for public
repos. On a private repo, a ~4.5 minute job every 5 minutes will burn
through the 2,000 free minutes/month quickly.

### Want zero gaps instead?

`scripts/poller.py` is kept in the repo as an optional drop-in replacement:
run it continuously on any always-on machine you control (PC, Pi, a free
Oracle Cloud VM) instead of relying on Actions' schedule. If you switch to
it, disable the "Burst-poll servers" step in `update.yml` so the two don't
overwrite each other's data.

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
`W_PING`). The frontend reads whatever weights `live.json` reports, so the
"RANK BY" note in the header stays in sync automatically. You can also
re-sort the board client-side by any single metric using the toolbar
buttons (Overall / Online / Daily peak / Uptime / Ping).

## Setup

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/<you>/minecraftasia.git
git push -u origin main
```

### 2. Enable GitHub Pages

Settings → Pages → Source: "Deploy from a branch" → Branch: `main`,
folder: `/ (root)` → Save. Site goes live at
`https://<you>.github.io/minecraftasia/` within a minute or two.

### 3. Let Actions write to the repo

Settings → Actions → General → "Workflow permissions" → select
**"Read and write permissions"** → Save. Without this, `update.yml`'s
final `git push` step will fail.

### 4. Confirm the workflow runs

Go to the **Actions** tab — you should see "Update rankings" scheduled
every 5 minutes. Click **Run workflow** to trigger it manually the first
time rather than waiting for the schedule, so you can confirm it works and
see real data land in `data/`.

### 5. Add or remove servers

Edit the `SERVERS` list in `scripts/common.py`. New servers automatically
get their own `data/history/<server>/` folder on the next run.

## Font

Server names, MOTDs, and numeric stats use **Monocraft**
(https://github.com/IdreesInc/Monocraft), a free MIT-licensed pixel font
inspired by Minecraft's own typeface, loaded from jsDelivr in
`css/style.css` — no download or build step needed. (Mojang's actual
"Minecraftia"/"Mojangles" typefaces aren't freely licensed for
redistribution, so this is the legal stand-in that looks the part.)

## Local preview

Because the page `fetch()`s local JSON files, opening `index.html` directly
(`file://`) will fail on CORS. Serve it locally instead:

```bash
python -m http.server 8000
# open http://localhost:8000
```

Until the workflow has run at least once, `data/live.json` is an empty
placeholder and the board will show nothing — that's expected, not a bug.
