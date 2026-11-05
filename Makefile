# ทางลัดคำสั่ง (Linux/macOS หรือ Windows ที่มี make) คำสั่งที่ต้องมีบริการจะใช้ได้เมื่อบริการพร้อม
SHELL := /bin/bash
.DEFAULT_GOAL := help
.PHONY: help up deploy build down logs test smoke

help:  ## แสดงรายการคำสั่ง
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-8s %s\n", $$1, $$2}'

up:  ## เปิดระบบทั้งชุด (docker compose)
	docker compose up -d --build --wait

deploy:  ## เปิดระบบบน VPS หลัง Caddy ของ video-buddy
	docker compose -f docker-compose.yml -f deploy/compose.server.yml up -d --build --wait

build:  ## build ภาพ Docker ใหม่โดยไม่เปิดระบบ
	docker compose build

down:  ## ปิดระบบ (ข้อมูลใน volume ยังอยู่)
	docker compose down

logs:  ## ดู log: make logs หรือ make logs s=api
	docker compose logs -f --tail=100 $(s)

test:  ## รันเทสต์ทุกบริการ
	python -m pytest services -q

smoke:  ## ทดสอบเร็วว่าระบบที่รันอยู่ตอบได้
	python3 scripts/smoke_test.py
