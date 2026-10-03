"""تست بار سبک (فقط کتابخانه استاندارد): چند کاربر هم‌زمان صفحه‌های اصلی را به‌صورت تصادفی باز می‌کنند.

    python scripts/loadtest.py --url https://shop.example.com --users 20 --seconds 30
    # مستقیم به gunicorn داخل شبکه docker (بدون محدودیت nginx):
    docker compose -f docker-compose.prod.yml run --rm --no-deps -T web python - \\
        --url http://web:8000 --host shop.example.com < scripts/loadtest.py

خروجی: تعداد درخواست در ثانیه، صدک‌های زمان پاسخ و تفکیک کدهای وضعیت.
"""

import argparse
import random
import ssl
import statistics
import threading
import time
import urllib.error
import urllib.request
from collections import Counter

PATHS = ["/", "/shop/", "/shop/?scent=woody", "/product/mystic-oud/", "/product/royal-saffron/",
         "/collections/", "/collections/oud/", "/blog/", "/about/", "/sitemap.xml"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--host", help="هدر Host (وقتی به آدرس داخلی وصل می‌شوید)")
    parser.add_argument("--users", type=int, default=20)
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--insecure", action="store_true", help="گواهی خودامضا را بپذیر")
    args = parser.parse_args()

    context = ssl._create_unverified_context() if args.insecure else None
    headers = {"User-Agent": "majd-loadtest", "X-Forwarded-Proto": "https"}
    if args.host:
        headers["Host"] = args.host
    latencies, codes, lock = [], Counter(), threading.Lock()
    deadline = time.monotonic() + args.seconds

    def user():
        while time.monotonic() < deadline:
            request = urllib.request.Request(args.url.rstrip("/") + random.choice(PATHS), headers=headers)
            started = time.monotonic()
            try:
                with urllib.request.urlopen(request, timeout=30, context=context) as response:
                    response.read()
                    code = response.status
            except urllib.error.HTTPError as exc:
                code = exc.code
            except Exception as exc:  # noqa: BLE001
                code = type(exc).__name__
            with lock:
                latencies.append((time.monotonic() - started) * 1000)
                codes[code] += 1

    threads = [threading.Thread(target=user) for _ in range(args.users)]
    started = time.monotonic()
    [t.start() for t in threads]
    [t.join() for t in threads]
    elapsed = time.monotonic() - started
    latencies.sort()

    def pct(p):
        return latencies[min(len(latencies) - 1, int(len(latencies) * p))]

    print(f"users={args.users} duration={elapsed:.1f}s requests={len(latencies)} rps={len(latencies) / elapsed:.1f}")
    print(f"latency ms: p50={pct(.50):.0f} p90={pct(.90):.0f} p95={pct(.95):.0f} p99={pct(.99):.0f} "
          f"max={latencies[-1]:.0f} mean={statistics.mean(latencies):.0f}")
    print("status:", dict(codes))


if __name__ == "__main__":
    main()
