"""
MinecraftAsia poller — OPTIONAL self-hosted alternative.

If you're using the GitHub-only setup (scripts/burst_poll.py run by
.github/workflows/update.yml), you do NOT need this file at all — it's kept
here in case you later want truly gapless, continuous 1-minute samples
instead of the small gaps that can occur between GitHub Actions bursts.

To use it: run it on any always-on machine you control (a PC, a Pi, a free
Oracle Cloud VM, etc). Make sure `git push` works from that machine without a
prompt (SSH deploy key or a stored HTTPS PAT), then stop/disable
update.yml's polling step so the two don't fight over the same files.

Usage:
    python -m pip install -r requirements.txt
    python scripts/poller.py
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as c

SAMPLE_INTERVAL_SEC = 60
PUSH_EVERY_N_SAMPLES = 5


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


def main():
    n = 0
    while True:
        n += 1
        try:
            ranked = c.sample_once()
            up = sum(1 for s in ranked if s["online_status"])
            print(f"[poller] sample #{n} — {up}/{len(ranked)} servers up")
            if n % PUSH_EVERY_N_SAMPLES == 0:
                stamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
                git_publish(f"data: live update {stamp}")
        except Exception as e:
            print("[poller] error:", e)
        time.sleep(SAMPLE_INTERVAL_SEC)


if __name__ == "__main__":
    main()
