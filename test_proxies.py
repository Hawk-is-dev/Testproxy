import os
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import requests

# ---- Settings (Railway Variables se change kar sakte ho) ----
TARGET = os.getenv("TARGET_URL", "https://api.ipify.org?format=json")
TIMEOUT = int(os.getenv("TIMEOUT", "15"))
INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))  # seconds; 0 = sirf ek baar
PROXY_TYPE = os.getenv("PROXY_TYPE", "socks5h")      # socks5h / socks5 / http
WORKERS = int(os.getenv("WORKERS", "20"))
FILE = os.getenv("PROXY_FILE", "proxies.txt")


def load_proxies():
    """Format: host:port:user:pass  ->  socks5h://user:pass@host:port"""
    # Agar PROXIES variable set hai toh pehle woh use hoga (alag lines ya comma)
    raw = os.getenv("PROXIES", "")
    if raw.strip():
        lines = raw.replace(",", "\n").splitlines()
    elif os.path.exists(FILE):
        with open(FILE) as f:
            lines = f.read().splitlines()
    else:
        lines = []

    proxies = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(":")
        if len(parts) != 4:
            print(f"Galat format, skip: {line[:40]}...", flush=True)
            continue
        host, port, user, pwd = parts
        url = f"{PROXY_TYPE}://{quote(user, safe='')}:{quote(pwd, safe='')}@{host}:{port}"
        proxies.append((line, url))
    return proxies


def short(line):
    # logs mein sirf session id dikhe, password nahi
    user = line.split(":")[2]
    return user.split("session-")[-1] if "session-" in user else user


def get_real_ip():
    try:
        return requests.get(TARGET, timeout=TIMEOUT).json().get("ip")
    except Exception:
        return None


def check(item, real_ip):
    line, url = item
    start = time.time()
    try:
        r = requests.get(TARGET, proxies={"http": url, "https": url}, timeout=TIMEOUT)
        ms = int((time.time() - start) * 1000)
        try:
            ip = r.json().get("ip")
        except Exception:
            ip = None
        if r.status_code != 200:
            return line, False, f"HTTP {r.status_code} | {ms}ms"
        if real_ip and ip == real_ip:
            return line, False, f"LEAK: proxy use nahi hua, asli IP dikha ({ip})"
        return line, True, f"{ms}ms | IP {ip}"
    except Exception as e:
        return line, False, f"{type(e).__name__}: {str(e)[:100]}"


def run_once():
    proxies = load_proxies()
    if not proxies:
        print("Koi proxy nahi mila. proxies.txt check karo.", flush=True)
        return
    real_ip = get_real_ip()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        results = list(ex.map(lambda p: check(p, real_ip), proxies))

    ok = [r for r in results if r[1]]
    print(
        f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} | Total: {len(results)} "
        f"| WORKING: {len(ok)} | FAILED: {len(results) - len(ok)} =====",
        flush=True,
    )
    for line, good, info in results:
        print(f"[{'WORKING' if good else 'FAILED '}] {short(line)} -> {info}", flush=True)

    print("\n--- Working proxies (copy karne ke liye) ---", flush=True)
    for line, good, _ in results:
        if good:
            print(line, flush=True)


if __name__ == "__main__":
    while True:
        run_once()
        if INTERVAL <= 0:
            break
        time.sleep(INTERVAL)
