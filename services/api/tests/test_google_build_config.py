"""ปุ่ม Google ในหน้าเว็บต้องได้ client ID ตอน build ใน Docker ด้วย ไม่งั้นตั้ง GOOGLE_CLIENT_ID แล้วปุ่มก็ไม่ขึ้น"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_compose_passes_google_client_id_to_web_build():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "VITE_GOOGLE_CLIENT_ID: ${GOOGLE_CLIENT_ID:-}" in compose


def test_web_dockerfile_exposes_build_arg_before_build():
    lines = (ROOT / "apps" / "web" / "Dockerfile").read_text(encoding="utf-8").splitlines()
    arg = lines.index("ARG VITE_GOOGLE_CLIENT_ID=")
    build = next(i for i, x in enumerate(lines) if "npm run build" in x)
    assert arg < build and "ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID" in lines[arg:build]
