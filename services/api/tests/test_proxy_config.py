"""nginx ต้องส่ง IP จริงของผู้ใช้ไปให้ API แทนค่าที่ผู้ใช้ส่งมาเอง

docker-compose ตั้ง FORWARDED_ALLOW_IPS="*" uvicorn จึงใช้ค่าแรกของ X-Forwarded-For เป็น IP ผู้ใช้
ถ้า nginx ต่อท้ายค่าเดิม ผู้ใช้ใส่ X-Forwarded-For ปลอมแล้วได้ IP ใหม่ทุกคำขอ หลบการจำกัดความถี่ของแชตได้
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _directives():
    conf = (ROOT / "apps" / "web" / "nginx.conf").read_text(encoding="utf-8")
    return [line.split("#", 1)[0].strip() for line in conf.splitlines() if line.split("#", 1)[0].strip()]


def test_nginx_overwrites_forwarded_for_with_real_ip():
    lines = _directives()
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in lines
    assert not any("$proxy_add_x_forwarded_for" in x for x in lines)


def test_uvicorn_takes_first_forwarded_for_entry():
    """ยืนยันพฤติกรรมของ uvicorn ที่เหตุผลข้างบนพึ่งพา (ถ้าเวอร์ชันใหม่เปลี่ยน เทสต์นี้จะเตือน)"""
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    mw = ProxyHeadersMiddleware(app=None, trusted_hosts="*")
    assert mw.get_trusted_client_host(["1.2.3.4", "5.6.7.8"]) == "1.2.3.4"
