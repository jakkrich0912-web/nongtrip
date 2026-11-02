"""วัดผลตัวค้นคืนกับชุดคำถามทดสอบ (ใช้ได้ทั้งชุดตัวอย่างและคลังจริง)

    python scripts/eval_retrieval.py                       # ชุดตัวอย่างในเทสต์
    python scripts/eval_retrieval.py --docs services/places/data/knowledge --golden tests/rag/golden.json

ตัวเลขที่จะขึ้นสไลด์ต้องมาจากการรันกับคลังจริงเท่านั้น (docs/RAG_PLAN.md ข้อ 8)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.places.retrieval import Retriever, evaluate  # noqa: E402

SAMPLE = ROOT / "services" / "places" / "tests" / "rag"
TARGET = 0.8


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--docs", default=str(SAMPLE / "sample_docs.json"), help="โฟลเดอร์คลัง (*.json) หรือไฟล์เดียว")
    ap.add_argument("--golden", default=str(SAMPLE / "golden_sample.json"))
    ap.add_argument("-k", type=int, default=3)
    a = ap.parse_args()
    docs_path = Path(a.docs)
    if docs_path.is_file():
        rt = Retriever(json.loads(docs_path.read_text(encoding="utf-8")).get("docs", []))
    else:
        rt = Retriever.from_dir(docs_path)
    cases = json.loads(Path(a.golden).read_text(encoding="utf-8"))["cases"]
    res = evaluate(rt, cases, k=a.k)
    print(f"คลัง {len(rt)} ก้อน, ชุดทดสอบ {len(cases)} ข้อ")
    if res["hit_at_k"] is not None:
        print(f"Hit@{res['k']}: {res['hit_at_k']:.0%} ({res['answerable']} ข้อที่มีคำตอบ) เป้า {TARGET:.0%}")
    if res["no_answer_ok"] is not None:
        print(f"ข้อที่คลังไม่ควรมีคำตอบ: ตอบว่าไม่มีถูก {res['no_answer_ok']:.0%} ({res['no_answer']} ข้อ)")
    for m in res["misses"]:
        print(f"  พลาด: {m['q']} -> ต้องได้ {m['expect']} ได้ {m['got']}")
    for f in res["false_hits"]:
        print(f"  ไม่ควรเจอ: {f['q']} -> {f['got']}")
    ok = (res["hit_at_k"] is None or res["hit_at_k"] >= TARGET) and not res["false_hits"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
