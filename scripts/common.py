"""
MinecraftAsia — shared config, probing, and scoring logic.
Used by both scripts/poller.py (continuous, self-hosted) and
scripts/aggregate.py (scheduled, runs in GitHub Actions).
"""
import json
import os
import socket
import time
import concurrent.futures

import requests

# ---------------- config ----------------
SERVERS = [
    "mazerclub.net", "mikitamc.ink", "kolap.net", "caffemc.xyz",
    "pkamc.vip", "friendlymc.vip", "rainomc.lol", "bejengmc.lol",
    "asiapvp.xyz", "doggysmp.ink", "asiaprac.xyz", "icemc.pro",
]
API = "https://api.mcsrvstat.us/3/{}"

# Ranking weights (must sum to 1.0)
W_ONLINE = 0.30   # current players online
W_DAILY  = 0.25   # 24h peak players
W_UPTIME = 0.25   # 24h uptime %
W_PING   = 0.20   # TCP ping

# Retention windows, in seconds
RAW_RETENTION_SEC    = 3 * 86400     # 3 days of true minute-level samples
HOURLY_RETENTION_SEC = 90 * 86400    # 90 days of hourly rollups
DAILY_RETENTION_SEC  = 400 * 86400   # ~13 months of daily rollups

ROOT_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR  = os.path.join(ROOT_DIR, "data")
HIST_DIR  = os.path.join(DATA_DIR, "history")
LIVE_PATH = os.path.join(DATA_DIR, "live.json")


# ---------------- probing ----------------
def tcp_ping(host, port, timeout=4):
    """Real TCP-connect latency to the minecraft port, in ms."""
    try:
        t0 = time.perf_counter()
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return round((time.perf_counter() - t0) * 1000, 1)
    except Exception:
        return None


def probe(addr):
    out = {"address": addr, "online_status": False, "players": 0, "max": 0,
           "ping_ms": None, "motd_html": [], "icon": None, "version": None}
    try:
        r = requests.get(API.format(addr), timeout=12)
        d = r.json()
    except Exception:
        return out
    if not d.get("online"):
        return out
    ip = d.get("ip", addr)
    port = d.get("port", 25565)
    version = d.get("version")
    if isinstance(version, dict):
        version = version.get("name")
    out.update({
        "online_status": True,
        "players": d.get("players", {}).get("online", 0),
        "max": d.get("players", {}).get("max", 0),
        "motd_html": d.get("motd", {}).get("html", [])[:2],
        "icon": d.get("icon"),
        "version": version,
        "ping_ms": tcp_ping(ip, port),
    })
    return out


def probe_all():
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        return list(ex.map(probe, SERVERS))


# ---------------- json helpers ----------------
def hist_path(server, name):
    d = os.path.join(HIST_DIR, server)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, name)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    os.replace(tmp, path)


# ---------------- scoring ----------------
def raw_uptime_pct(raw_records, since_ts):
    recs = [r for r in raw_records if r["ts"] >= since_ts]
    if not recs:
        return None
    ups = sum(1 for r in recs if r["up"])
    return round(100 * ups / len(recs), 2)


def daily_peak(raw_records, since_ts):
    recs = [r for r in raw_records if r["ts"] >= since_ts]
    if not recs:
        return 0
    return max(r["online"] for r in recs)


def sample_once():
    """Probe every server once, append to each server's raw history, and
    write a fresh data/live.json. Used by both scripts/poller.py (continuous,
    self-hosted) and scripts/burst_poll.py (short bursts inside a GitHub
    Actions run). Returns the ranked results list."""
    results = probe_all()
    ts = int(time.time())

    raw_by_server = {}
    for s in results:
        path = hist_path(s["address"], "raw.json")
        data = load_json(path, [])
        data.append({
            "ts": ts,
            "online": s["players"],
            "ping": s["ping_ms"],
            "up": 1 if s["online_status"] else 0,
        })
        cutoff = ts - RAW_RETENTION_SEC
        data = [r for r in data if r["ts"] >= cutoff]
        save_json(path, data)
        raw_by_server[s["address"]] = data

    ranked = compute_ranking(results, raw_by_server)
    save_json(LIVE_PATH, {
        "updated": ts,
        "weights": {"online": W_ONLINE, "daily": W_DAILY, "uptime": W_UPTIME, "ping": W_PING},
        "servers": ranked,
    })
    return ranked


def compute_ranking(results, raw_by_server):
    """results: list of probe() outputs. raw_by_server: address -> list of
    {ts, online, ping, up} raw samples (including the one just taken)."""
    now = int(time.time())
    day_ago = now - 86400

    for s in results:
        raw = raw_by_server.get(s["address"], [])
        s["daily_peak"] = daily_peak(raw, day_ago) if raw else s["players"]
        uptime = raw_uptime_pct(raw, day_ago)
        s["uptime_24h"] = uptime if uptime is not None else (100.0 if s["online_status"] else 0.0)

    max_online = max([s["players"] for s in results] + [1])
    max_daily  = max([s["daily_peak"] for s in results] + [1])
    pings = [s["ping_ms"] for s in results if s["ping_ms"] is not None]
    worst_ping = max(pings) if pings else 500

    for s in results:
        if not s["online_status"]:
            s["score_online"] = s["score_daily"] = s["score_ping"] = 0.0
        else:
            s["score_online"] = round(100 * s["players"] / max_online, 1)
            s["score_daily"]  = round(100 * s["daily_peak"] / max_daily, 1)
            p = s["ping_ms"] if s["ping_ms"] is not None else worst_ping
            s["score_ping"]   = round(100 * (1 - min(p, 500) / 500), 1)
        s["score_uptime"] = round(s["uptime_24h"], 1)
        s["overall"] = round(
            W_ONLINE * s["score_online"] +
            W_DAILY  * s["score_daily"]  +
            W_UPTIME * s["score_uptime"] +
            W_PING   * s["score_ping"], 1
        )

    results.sort(key=lambda s: s["overall"], reverse=True)
    for i, s in enumerate(results, 1):
        s["rank"] = i
    return results
