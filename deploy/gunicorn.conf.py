"""پیکربندی gunicorn (production). همه مقادیر با متغیر محیطی قابل تغییرند."""

import multiprocessing
import os

bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")
# پیش‌فرض: 2×CPU+1 (حداکثر ۹)؛ برای کانتینر با محدودیت CPU مقدار WEB_CONCURRENCY را صریح بدهید
workers = int(os.environ.get("WEB_CONCURRENCY", min(multiprocessing.cpu_count() * 2 + 1, 9)))
threads = int(os.environ.get("GUNICORN_THREADS", 2))
worker_class = "gthread"
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 30))
graceful_timeout = 30
keepalive = 5
# بازنشانی دوره‌ای workerها جلوی رشد تدریجی حافظه را می‌گیرد
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = 100
worker_tmp_dir = "/dev/shm"  # heartbeat روی حافظه، نه دیسک overlay کانتینر

# gunicorn فقط از داخل شبکه docker (پشت nginx) در دسترس است؛ پورت آن منتشر نمی‌شود
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "*")
proxy_allow_ips = forwarded_allow_ips

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info").lower()
access_log_format = '{"time":"%(t)s","request_id":"%({x-request-id}i)s","ip":"%({x-forwarded-for}i)s",' \
                    '"method":"%(m)s","path":"%(U)s","status":%(s)s,"bytes":%(B)s,"duration_ms":%(M)s}'
