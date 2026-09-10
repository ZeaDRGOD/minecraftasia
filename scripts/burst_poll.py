"""
MinecraftAsia burst poller — designed to run INSIDE a GitHub Actions job
(.github/workflows/update.yml), not on your own machine.

A single Actions run can't stay alive forever, but it can stay alive for a
few minutes. This script takes BURST_SAMPLES samples, spaced
SAMPLE_INTERVAL_SEC apart, all within one job run — giving you real
minute-level data for that window. The workflow then commits everything in
one shot. Between runs there can be a small gap (GitHub's schedule has a
5-minute floor and can slip further under load), but within a run the data
is genuinely per-minute.

If you need zero gaps at all, run scripts/poller.py continuously on your own
always-on machine instead (see its docstring), and disable the polling step
in update.yml so the two don't write conflicting data.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as c

BURST_SAMPLES = 4          # samples taken per Actions run
SAMPLE_INTERVAL_SEC = 60   # real per-minute spacing between them


def main():
    for i in range(1, BURST_SAMPLES + 1):
        try:
            ranked = c.sample_once()
            up = sum(1 for s in ranked if s["online_status"])
            print(f"[burst_poll] sample {i}/{BURST_SAMPLES} — {up}/{len(ranked)} servers up")
        except Exception as e:
            print(f"[burst_poll] sample {i}/{BURST_SAMPLES} error:", e)
        if i < BURST_SAMPLES:
            time.sleep(SAMPLE_INTERVAL_SEC)


if __name__ == "__main__":
    main()
