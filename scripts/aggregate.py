"""
MinecraftAsia aggregator — run on a schedule via GitHub Actions
(.github/workflows/aggregate.yml).

Rolls the poller's raw minute-level samples into hourly buckets, hourly
buckets into daily buckets, and prunes data past its retention window so
the repo doesn't grow forever. Safe to run as often as you like; it's
idempotent (it upserts buckets by timestamp rather than duplicating).
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as c


def bucket_stats(records):
    ups = [r for r in records if r["up"]]
    online_vals = [r["online"] for r in records]
    ping_vals = [r["ping"] for r in ups if r.get("ping") is not None]
    return {
        "avg_online": round(sum(online_vals) / len(online_vals), 1) if online_vals else 0,
        "peak_online": max(online_vals) if online_vals else 0,
        "avg_ping": round(sum(ping_vals) / len(ping_vals), 1) if ping_vals else None,
        "uptime_pct": round(100 * len(ups) / len(records), 1) if records else 0,
    }


def rollup(records, bucket_seconds):
    buckets = {}
    for r in records:
        b = r["ts"] - (r["ts"] % bucket_seconds)
        buckets.setdefault(b, []).append(r)
    return [{"ts": b, **bucket_stats(recs)} for b, recs in sorted(buckets.items())]


def process_server(server, now):
    raw_path = c.hist_path(server, "raw.json")
    raw = c.load_json(raw_path, [])

    # --- raw -> hourly (upsert by bucket timestamp) ---
    hourly_path = c.hist_path(server, "hourly.json")
    hourly_map = {h["ts"]: h for h in c.load_json(hourly_path, [])}
    for h in rollup(raw, 3600):
        hourly_map[h["ts"]] = h
    hourly = sorted(hourly_map.values(), key=lambda x: x["ts"])
    hourly = [h for h in hourly if h["ts"] >= now - c.HOURLY_RETENTION_SEC]
    c.save_json(hourly_path, hourly)

    # --- hourly -> daily (upsert by bucket timestamp) ---
    daily_path = c.hist_path(server, "daily.json")
    daily_map = {d["ts"]: d for d in c.load_json(daily_path, [])}
    day_buckets = {}
    for h in hourly:
        b = h["ts"] - (h["ts"] % 86400)
        day_buckets.setdefault(b, []).append(h)
    for b, hrs in day_buckets.items():
        pings = [h["avg_ping"] for h in hrs if h["avg_ping"] is not None]
        daily_map[b] = {
            "ts": b,
            "avg_online": round(sum(h["avg_online"] for h in hrs) / len(hrs), 1),
            "peak_online": max(h["peak_online"] for h in hrs),
            "avg_ping": round(sum(pings) / len(pings), 1) if pings else None,
            "uptime_pct": round(sum(h["uptime_pct"] for h in hrs) / len(hrs), 1),
        }
    daily = sorted(daily_map.values(), key=lambda x: x["ts"])
    daily = [d for d in daily if d["ts"] >= now - c.DAILY_RETENTION_SEC]
    c.save_json(daily_path, daily)

    # --- prune raw (defense in depth; the poller already prunes on write) ---
    raw = [r for r in raw if r["ts"] >= now - c.RAW_RETENTION_SEC]
    c.save_json(raw_path, raw)


def main():
    now = int(time.time())
    for server in c.SERVERS:
        try:
            process_server(server, now)
            print(f"[aggregate] {server} ok")
        except Exception as e:
            print(f"[aggregate] {server} error:", e)


if __name__ == "__main__":
    main()
