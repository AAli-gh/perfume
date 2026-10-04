# دستورهای رایج توسعه و استقرار (راهنمای کامل: README.md و DEPLOY.md)
PY ?= python
COMPOSE_PROD = docker compose -f docker-compose.prod.yml

.PHONY: help css test e2e lint lock build up down logs smoke backup loadtest

help:  ## فهرست دستورها
	@grep -E '^[a-z0-9-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

css:  ## ساخت CSS با Tailwind
	npm run build:css

test:  ## تست‌های واحد و یکپارچگی با پوشش کد
	$(PY) -m pytest --cov

e2e: css  ## تست‌های سرتاسری با مرورگر
	$(PY) -m pytest -m e2e

lint:  ## بررسی کد
	ruff check .

lock:  ## به‌روزرسانی requirements.lock (Python 3.12، لینوکس، با hash) از روی requirements.txt
	uv pip compile requirements.txt --python-version 3.12 --python-platform x86_64-manylinux_2_28 \
		--generate-hashes --no-header -o requirements.lock

build:  ## ساخت image production
	docker build -t $${APP_IMAGE:-majd:latest} .

up:  ## اجرای stack production (نیاز به .env و deploy/certs)
	$(COMPOSE_PROD) up -d

down:  ## توقف stack
	$(COMPOSE_PROD) down

logs:  ## لاگ سرویس‌ها
	$(COMPOSE_PROD) logs -f --tail 100

smoke:  ## آزمون دود؛ مثال: make smoke URL=https://shop.example.com
	sh deploy/smoke-test.sh $${URL:-https://localhost} $${INSECURE:+--insecure}

backup:  ## پشتیبان‌گیری فوری
	$(COMPOSE_PROD) exec -T backup sh /scripts/backup.sh once

loadtest:  ## تست بار مستقیم روی gunicorn (بدون محدودیت nginx)
	$(COMPOSE_PROD) run --rm --no-deps -T web python - --url http://web:8000 --host $${HOST:-localhost} \
		--users $${USERS:-20} --seconds $${DURATION:-30} < scripts/loadtest.py
