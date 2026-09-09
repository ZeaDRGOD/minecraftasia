"""
MinecraftAsia poller — self-hosted, continuous.

GitHub Actions cannot reliably run more often than every 5 minutes, so this
script is meant to run somewhere always-on that YOU control: your own PC, a
Raspberry Pi, a free-tier Oracle Cloud VM, a small always-free Fly.io/Render
worker, etc. It gives you real 60-second samples and pushes them to your
GitHub repo every 5 minutes, which is what GitHub Pages then serves.

Usage:
    cd minecraftasia
    python -m pip install requests
    python scripts/poller.py

Recommended: run it under systemd, pm2, or a `screen`/`tmux` session so it
survives reboots. Make sure `git` in that directory can push without a
password prompt (SSH deploy key, or a stored HTTPS credential/PAT).
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as c

SAMPLE_INTERVAL_SEC = 60   # true per-minute samples
PUSH_EVERY_N_SAMPLES = 5   # push to git roughly every 5 minutes


def append_raw(server, record):
    path = c.hist_path(server, "raw.json")
    data = c.load_json(path, [])
    data.append(record)
    cutoff = record["ts"] - c.RAW_RETENTION_SEC
    data = [r for r in data if r["ts"] >= cutoff]
    c.save_json(path, data)
    return data


def git_publish(message):
    try:
        subprocess.run(["git", "add", "data"], cwd=c.ROOT_DIR, check=True)
        unchanged = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=c.ROOT_DIR
        ).returncode == 0
        if unchanged:
            return
        subprocess.run(["git", "commit", "-m", message], cwd=c.ROOT_DIR, check=True)
        subprocess.run(["git", "push"], cwd=c.ROOT_DIR, check=True)
        print(f"[poller] pushed: {message}")
    except subprocess.CalledProcessError as e:
        print("[poller] git error:", e)


def run_once(sample_no):
    results = c.probe_all()
    ts = int(time.time())

    raw_by_server = {}
    for s in results:
        record = {
            "ts": ts,
            "online": s["players"],
            "ping": s["ping_ms"],
            "up": 1 if s["online_status"] else 0,
        }
        raw_by_server[s["address"]] = append_raw(s["address"], record)

    ranked = c.compute_ranking(results, raw_by_server)
    c.save_json(c.LIVE_PATH, {
        "updated": ts,
        "weights": {
            "online": c.W_ONLINE, "daily": c.W_DAILY,
            "uptime": c.W_UPTIME, "ping": c.W_PING,
        },
        "servers": ranked,
    })

    up_count = sum(1 for s in ranked if s["online_status"])
    print(f"[poller] sample #{sample_no} — {up_count}/{len(ranked)} servers up")

    if sample_no % PUSH_EVERY_N_SAMPLES == 0:
        stamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(ts))
        git_publish(f"data: live update {stamp}")


def main():
    c.load_json(c.LIVE_PATH, {})  # touch, ensures data dir logic runs once
    n = 0
    while True:
        n += 1
        try:
            run_once(n)
        except Exception as e:
            print("[poller] error:", e)
        time.sleep(SAMPLE_INTERVAL_SEC)


if __name__ == "__main__":
    main()
