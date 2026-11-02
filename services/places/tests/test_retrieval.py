import json
from pathlib import Path

import pytest

from services.places import knowledge as k
from services.places import retrieval as r

RAG = Path(__file__).parent / "rag"
DOCS = json.loads((RAG / "sample_docs.json").read_text(encoding="utf-8"))["docs"]
CASES = json.loads((RAG / "golden_sample.json").read_text(encoding="utf-8"))["cases"]


@pytest.fixture(scope="module")
def rt():
    return r.Retriever(DOCS)


def test_tokens_thai_trigram_and_short_runs():
    # นับเป็นตัวอักษร Unicode (สระ/วรรณยุกต์นับด้วย) วัดป่า = 6 ตัว -> 4 กลุ่ม
    assert r.tokens("วัดป่า") == ["วัด", "ัดป", "ดป่", "ป่า"]
    assert r.tokens("วัด") == ["วัด"]
    assert r.tokens("ก") == []            # ตัวอักษรเดี่ยวไม่เก็บ


def test_tokens_english_and_mixed():
    assert r.tokens("The Old Market 2026") == ["old", "market", "2026"]
    t = r.tokens("วัด Doi Suthep, เชียงใหม่")
    assert "doi" in t and "suthep" in t and "วัด" in t and "เชี" in t


def test_tokens_none_and_symbols():
    assert r.tokens("") == [] and r.tokens(None) == []
    assert r.tokens("!!! ??? ...") == []


def test_len_and_skips_bad_docs():
    rt2 = r.Retriever(DOCS + [{"id": "", "text": "x"}, {"id": "k:x:0", "text": ""}])
    assert len(rt2) == len(DOCS)


def test_golden_hit_at_3_and_no_answer(rt):
    res = r.evaluate(rt, CASES, k=3)
    assert res["hit_at_k"] >= 0.8, res["misses"]
    assert res["no_answer_ok"] == 1.0, res["false_hits"]


def test_each_golden_answerable_hits_at_1(rt):
    # ชุดตัวอย่างเล็กและแยกชัด ควรได้ที่ 1 ทุกข้อ ถ้าตกแปลว่าสูตรคะแนนเสื่อม
    for c in CASES:
        if not c["expect"]:
            continue
        top = rt.search(c["q"], c.get("place_ids"), k=1)
        assert top and top[0]["doc"]["id"] == c["expect"], c["q"]


def test_place_filter_limits_results(rt):
    got = rt.search("วัดป่าสนธาร", place_ids=["v:t01"])
    assert got and {h["doc"]["place_id"] for h in got} == {"v:t01"}
    assert rt.search("วัดป่าสนธาร", place_ids=["v:t04"]) == []
    assert rt.search("วัดป่าสนธาร", place_ids=[]) == []
    assert rt.search("วัดป่าสนธาร", place_ids=["v:none"]) == []


def test_results_sorted_and_k_limit(rt):
    got = rt.search("น้ำตกศรีภูผา", k=2)
    assert len(got) <= 2
    assert [h["score"] for h in got] == sorted((h["score"] for h in got), reverse=True)
    assert rt.search("น้ำตกศรีภูผา", k=0) == []


def test_empty_query_and_empty_index():
    assert r.Retriever([]).search("วัด") == []
    assert r.Retriever(DOCS).search("") == []
    assert r.Retriever(DOCS).search("!!!") == []


def test_unknown_words_give_no_hits(rt):
    assert rt.search("zzzqqq xxyyww") == []


def test_title_boost_prefers_named_place(rt):
    top = rt.search("ถ้ำลมเย็น", k=1)
    assert top[0]["doc"]["id"] == "k:t04:0"


def test_deterministic_ties():
    a = {"id": "k:a:0", "place_id": "v:a", "title": "ก", "text": "น้ำตกสวยงามมาก"}
    b = {"id": "k:b:0", "place_id": "v:b", "title": "ก", "text": "น้ำตกสวยงามมาก"}
    ids = [h["doc"]["id"] for h in r.Retriever([b, a]).search("น้ำตกสวยงาม")]
    assert ids == ["k:a:0", "k:b:0"]


def test_fit_context_caps_chars_and_skips_overflow():
    def hit(i, n):
        return {"doc": {"id": f"k:{i}", "text": "ก" * n}, "score": 1.0, "coverage": 1.0}
    got = r.fit_context([hit(1, 1500), hit(2, 1500), hit(3, 1500), hit(4, 400)], max_chars=4000)
    assert [h["doc"]["id"] for h in got] == ["k:1", "k:2", "k:4"]
    assert sum(len(h["doc"]["text"]) for h in got) <= 4000
    assert r.fit_context([]) == []


def test_default_context_budget_holds_top_k_of_max_size_chunks():
    assert r.TOP_K * k.MAX_CHARS >= r.MAX_CONTEXT_CHARS - k.MAX_CHARS   # เพดาน 4,000 ตัดจริงเมื่อก้อนเต็ม
    assert r.MAX_CONTEXT_CHARS == 4000 and r.TOP_K == 4


def test_source_items_dedupe_and_fields(rt):
    hits = rt.search("น้ำตกศรีภูผา")
    items = r.source_items(hits + hits)
    assert len({i["id"] for i in items}) == len(items)
    assert set(items[0]) == {"id", "place_id", "title", "url", "license", "checked_on"}
    assert all(i["license"] == "CC BY-SA 4.0" for i in items)


def test_from_dir_roundtrip(tmp_path):
    k.write_province(tmp_path, "ทดสอบ", DOCS, "2026-11-05")
    rt2 = r.Retriever.from_dir(tmp_path)
    assert len(rt2) == len(DOCS)
    assert rt2.search("ถ้ำลมเย็น", k=1)[0]["doc"]["id"] == "k:t04:0"
    assert len(r.Retriever.from_dir(tmp_path / "ไม่มี")) == 0


def test_sample_docs_obey_knowledge_rules():
    known = {d["place_id"] for d in DOCS}
    assert k.validate(DOCS, known) == []


def test_evaluate_reports_misses_and_false_hits(rt):
    res = r.evaluate(rt, [{"q": "ถ้ำลมเย็น", "expect": "k:t01:0"}, {"q": "วัดป่าสนธาร", "expect": None}])
    assert res["hit_at_k"] == 0.0 and res["misses"][0]["expect"] == "k:t01:0"
    assert res["no_answer_ok"] == 0.0 and res["false_hits"]
