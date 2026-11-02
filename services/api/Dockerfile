# API กลางของน้องทริป (รวมบริการค้นสถานที่ services/places) build จากโฟลเดอร์รากของ repo
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/api/requirements.txt services/api/requirements.txt
COPY services/places/requirements.txt services/places/requirements.txt
RUN pip install --no-cache-dir -r services/api/requirements.txt -r services/places/requirements.txt

COPY services ./services

# ฐานข้อมูลผู้ใช้ (SQLite) และแคชค้นหาเก็บใน /data ซึ่งเป็น volume ให้ข้อมูลอยู่รอดเมื่อสร้างคอนเทนเนอร์ใหม่
RUN useradd --system --uid 10001 app && mkdir -p /data && chown app /data
ENV DB_PATH=/data/nongtrip.db \
    PLACES_CACHE_DIR=/data/cache
VOLUME /data
USER app

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=4s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

CMD ["python", "-m", "uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
