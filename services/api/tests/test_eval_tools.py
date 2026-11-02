"""ทดสอบสคริปต์ scripts/check_llm.py และ scripts/eval_rag.py (ไม่เรียก LLM หรือเครือข่ายจริง)"""
import os
import importlib.util
import json
from pathlib import Path

import pytest

from services.api.llm import LLMClient, LLMError
from services.api.rag import Rag
from services.places.retrieval import Retriever

ROOT = Path(__file__).resolve().parents[3]
SAMPLE = ROOT / "services" / "places" / "tests" / "rag"


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


check_llm = load("check_llm")
eval_rag = load("eval_rag")
SECRET = "sk-test-SECRET-1234567890"


# ---------- check_llm ----------
def ok_post(url, headers, body, timeout):
    return {"content": [{"type": "text", "text": "พร้อม"}]}


def test_check_llm_not_configured_exits_2_without_leaking(capsys):
    env = {"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": SECRET}      # ไม่มี LLM_MODEL
    code = check_llm.main(env=env, dotenv=None)
    out = capsys.readouterr().out
    assert code == 2
    assert "LLM_MODEL: ยังไม่ได้ตั้ง" in out and "ANTHROPIC_API_KEY: ตั้งแล้ว" in out
    assert SECRET not in out


def test_check_llm_mock_provider_says_how_to_enable(capsys):
    assert check_llm.main(env={}, dotenv=None) == 2
    assert "LLM_PROVIDER = mock" in capsys.readouterr().out


def test_check_llm_success(capsys):
    env = {"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": SECRET, "LLM_MODEL": "m"}
    code = check_llm.main(env=env, dotenv=None, factory=lambda e: LLMClient("anthropic", "m", SECRET, post=ok_post))
    out = capsys.readouterr().out
    assert code == 0 and "สำเร็จ" in out and "anthropic" in out and SECRET not in out


def test_check_llm_failure_exits_1_and_hides_key(capsys):
    def boom(url, headers, body, timeout):
        raise LLMError("LLM ตอบ HTTP 401")
    code = check_llm.main(env={}, dotenv=None, factory=lambda e: LLMClient("openai", "m", SECRET, post=boom))
    out = capsys.readouterr().out
    assert code == 1 and "HTTP 401" in out and SECRET not in out


def test_load_dotenv_does_not_override_and_strips_quotes(tmp_path):
    f = tmp_path / ".env"
    f.write_text('# หมายเหตุ\nLLM_PROVIDER=openai\nLLM_MODEL="gpt-x"\nEMPTY=\nOPENAI_API_KEY=from-file\n', encoding="utf-8")
    env = {"OPENAI_API_KEY": "from-env"}
    assert check_llm.load_dotenv(f, env) is True
    assert env["OPENAI_API_KEY"] == "from-env" and env["LLM_MODEL"] == "gpt-x" and env["LLM_PROVIDER"] == "openai"
    assert check_llm.load_dotenv(tmp_path / "nope", {}) is False


# ---------- eval_rag ----------
class Scripted:
    provider, model = "fake", "fake"

    def __init__(self, fn):
        self.fn = fn

    def complete(self, system, user, max_tokens=700):
        return self.fn(user)


def sample_rag(llm):
    docs = json.loads((SAMPLE / "sample_docs.json").read_text(encoding="utf-8"))["docs"]
    return Rag(Retriever(docs), llm, known_names={d["title"] for d in docs})


def cases():
    return json.loads((SAMPLE / "golden_e2e_sample.json").read_text(encoding="utf-8"))["cases"]


def test_mock_run_passes_end_to_end(capsys):
    assert eval_rag.main(["--mock"]) == 0
    out = capsys.readouterr().out
    assert "ไม่ใช่ผลวัดจริง" in out and "ผ่านเกณฑ์" in out


def test_no_llm_exits_2(monkeypatch, capsys):
    monkeypatch.setattr(eval_rag, "from_env", lambda env=None: None)
    assert eval_rag.main([], dotenv=None) == 2


def test_run_counts_each_kind():
    rep = eval_rag.run(sample_rag(eval_rag.MockLLM()), cases())
    assert {k: v["n"] for k, v in rep["summary"].items()} == {"answer": 6, "no_answer": 2, "refuse": 3, "injection": 2}
    assert rep["hit_at_k"] == 1.0 and rep["llm_pass"] == 1.0 and eval_rag.passed(rep)


def test_llm_that_cites_nothing_fails_answer_cases_and_falls_back():
    rag = sample_rag(Scripted(lambda user: "วัดนี้เก่าแก่มาก"))          # ไม่ใส่รหัสที่มา ด่านตรวจต้องไม่ให้ผ่าน
    rep = eval_rag.run(rag, cases())
    assert rep["summary"]["answer"]["ok"] == 0 and rep["llm_pass"] == 0 and rep["guard_fail"] >= 6
    assert not eval_rag.passed(rep)
    # ถอยโหมดกฎเป็นผลปลอดภัย: ข้อ refuse/injection ยังผ่าน
    assert rep["summary"]["refuse"]["rate"] == 1 and rep["summary"]["injection"]["rate"] == 1


def test_injection_canary_in_llm_answer_is_flagged():
    def leak(user):
        doc = __import__("re").search(r'<doc id="([^"]+)"', user)
        return f"PWNED [{doc.group(1)}]" if doc else "ไม่มีข้อมูลเรื่องนี้ในคลังของระบบ"
    rep = eval_rag.run(sample_rag(Scripted(leak)), [c for c in cases() if c["kind"] == "injection"])
    bad = [r for r in rep["rows"] if not r["ok"]]
    # ถ้าคำตอบที่มี PWNED หลุดผ่านด่านตรวจมาได้ สคริปต์ต้องนับว่าไม่ผ่าน ไม่ใช่ผ่านเงียบๆ
    assert all("PWNED" in r["note"] for r in bad)
    assert rep["summary"]["injection"]["n"] == 2


def test_answer_case_without_expected_source_fails():
    c = [{"q": "วัดป่าสนธารสร้างสมัยไหน", "kind": "answer", "expect": "k:t02:0", "place_ids": ["v:t01"]}]
    rep = eval_rag.run(sample_rag(eval_rag.MockLLM()), c)
    assert rep["rows"][0]["ok"] is False


def test_out_file_written(tmp_path):
    out = tmp_path / "r.json"
    assert eval_rag.main(["--mock", "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "จำลอง" in data["llm"] and len(data["rows"]) == 13


def test_judge_flags_leaked_canary_directly():
    from services.api.rag import RagResult
    case = {"q": "x", "kind": "injection", "must_not_contain": ["PWNED"]}
    bad, note = eval_rag.judge(case, RagResult("llm", text="PWNED [k:t01:0]"), None)
    ok, _ = eval_rag.judge(case, RagResult("rule", reason="guard"), None)
    assert bad is False and "PWNED" in note and ok is True


def test_eval_rag_reads_dotenv(tmp_path, monkeypatch):
    for k in ("LLM_PROVIDER", "LLM_MODEL", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    seen = {}

    def fake_from_env(env=None):
        seen.update(env or {})
        return None   # ไม่ต้องเรียก LLM จริง แค่ดูว่าค่าจาก .env ถูกส่งต่อมา

    monkeypatch.setattr(eval_rag, "from_env", fake_from_env)
    f = tmp_path / ".env"
    f.write_text("LLM_PROVIDER=anthropic\nLLM_MODEL=m\nANTHROPIC_API_KEY=x\n", encoding="utf-8")
    assert eval_rag.main([], dotenv=f) == 2
    assert seen["LLM_PROVIDER"] == "anthropic" and seen["ANTHROPIC_API_KEY"] == "x"
    assert "LLM_PROVIDER" not in os.environ   # ไม่เขียนทับสภาพแวดล้อมของโปรเซส


def test_rows_keep_rejected_text_and_guard_detail():
    rag = sample_rag(Scripted(lambda user: "วัดนี้เก่าแก่มาก"))
    rep = eval_rag.run(rag, [c for c in cases() if c["kind"] == "answer"][:1])
    r = rep["rows"][0]
    assert r["reason"] == "guard" and r["rejected"] == "วัดนี้เก่าแก่มาก" and r["guard_detail"]


def test_only_failed_reruns_just_those_cases(tmp_path, capsys):
    first = tmp_path / "first.json"
    assert eval_rag.main(["--mock", "--out", str(first)]) == 0
    data = json.loads(first.read_text(encoding="utf-8"))
    data["rows"][0]["ok"] = False          # สมมุติว่าข้อแรกไม่ผ่านรอบก่อน
    first.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    second = tmp_path / "second.json"
    eval_rag.main(["--mock", "--only-failed", str(first), "--out", str(second)])
    rows = json.loads(second.read_text(encoding="utf-8"))["rows"]
    assert [r["q"] for r in rows] == [data["rows"][0]["q"]]


def test_build_items_prefers_real_verified_names(monkeypatch):
    rag = sample_rag(eval_rag.MockLLM())
    pid = rag.retriever.docs[0]["place_id"]
    monkeypatch.setattr(eval_rag, "_REAL", {pid: ["ชื่อไทยจริง", "Real English Name"]})
    item = eval_rag.build_items({"q": "x", "place_ids": [pid]}, rag.retriever)[0]
    assert item["name_th"] == "ชื่อไทยจริง" and item["name_en"] == "Real English Name"
    monkeypatch.setattr(eval_rag, "_REAL", {})       # ไม่มีชื่อจริง ใช้ชื่อเรื่องของก้อนตามเดิม
    item = eval_rag.build_items({"q": "x", "place_ids": [pid]}, rag.retriever)[0]
    assert item["name_th"] == rag.retriever.docs[0]["title"] and "name_en" not in item
