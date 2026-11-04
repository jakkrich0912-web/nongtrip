import io
import json
import urllib.error

import pytest

from services.api import llm
from services.api.llm import LLMClient, LLMError, from_env

KEY = "sk-test-SECRET-123"


def fake_post(responses, calls):
    it = iter(responses)

    def post(url, headers, body, timeout):
        calls.append((url, dict(headers), body, timeout))
        r = next(it)
        if isinstance(r, Exception):
            raise r
        return r
    return post


ANTH_OK = {"content": [{"type": "text", "text": "สวัสดี "}, {"type": "tool_use", "id": "x"}, {"type": "text", "text": "ครับ"}]}
OPENAI_OK = {"choices": [{"message": {"content": "  คำตอบ  "}}]}


def test_anthropic_request_and_response():
    calls = []
    c = LLMClient("anthropic", "m1", KEY, post=fake_post([ANTH_OK], calls))
    assert c.complete("SYS", "USER") == "สวัสดี ครับ"
    url, headers, body, timeout = calls[0]
    assert url == llm.ANTHROPIC_URL and headers["x-api-key"] == KEY and headers["anthropic-version"]
    assert body["model"] == "m1" and body["system"] == "SYS" and body["messages"] == [{"role": "user", "content": "USER"}]
    assert body["max_tokens"] == llm.MAX_TOKENS and timeout == 30


def test_openai_request_and_response():
    calls = []
    c = LLMClient("openai", "m2", KEY, post=fake_post([OPENAI_OK], calls))
    assert c.complete("SYS", "USER", max_tokens=50) == "คำตอบ"
    url, headers, body, _ = calls[0]
    assert url == llm.OPENAI_URL and headers["Authorization"] == f"Bearer {KEY}"
    assert body["messages"] == [{"role": "system", "content": "SYS"}, {"role": "user", "content": "USER"}] and body["max_tokens"] == 50


def test_retry_once_on_retryable_then_success():
    calls = []
    post = fake_post([LLMError("503", retryable=True), ANTH_OK], calls)
    assert LLMClient("anthropic", "m", KEY, post=post).complete("s", "u") == "สวัสดี ครับ"
    assert len(calls) == 2


def test_gives_up_after_one_retry():
    calls = []
    post = fake_post([LLMError("a", True), LLMError("b", True), ANTH_OK], calls)
    with pytest.raises(LLMError, match="b"):
        LLMClient("anthropic", "m", KEY, post=post).complete("s", "u")
    assert len(calls) == 2


def test_no_retry_on_non_retryable():
    calls = []
    with pytest.raises(LLMError):
        LLMClient("openai", "m", KEY, post=fake_post([LLMError("401"), OPENAI_OK], calls)).complete("s", "u")
    assert len(calls) == 1


@pytest.mark.parametrize("data", [
    {}, {"content": []}, {"content": [{"type": "text", "text": "  "}]}, {"content": "x"}, {"content": [None]},
    {"choices": []}, {"choices": [{"message": {}}]}, {"choices": [{"message": {"content": None}}]}, {"choices": [{"message": {"content": 5}}]},
])
def test_bad_response_shapes_raise(data):
    for provider in ("anthropic", "openai"):
        with pytest.raises(LLMError):
            LLMClient(provider, "m", KEY, retries=0, post=fake_post([data], [])).complete("s", "u")


def test_unknown_provider_rejected():
    with pytest.raises(ValueError):
        LLMClient("foo", "m", KEY)


def test_repr_never_contains_key_and_errors_do_not_leak_it():
    c = LLMClient("openai", "m", KEY)
    assert KEY not in repr(c) and KEY not in str(c)
    try:
        LLMClient("openai", "m", KEY, post=fake_post([{"choices": []}], []), retries=0).complete("s", "u")
    except LLMError as e:
        assert KEY not in str(e)


@pytest.mark.parametrize("env,expect", [
    ({}, None),
    ({"LLM_PROVIDER": "mock"}, None),
    ({"LLM_PROVIDER": "MOCK", "ANTHROPIC_API_KEY": KEY, "LLM_MODEL": "m"}, None),
    ({"LLM_PROVIDER": "anthropic", "LLM_MODEL": "m"}, None),                          # ไม่มีคีย์
    ({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": KEY}, None),                  # ไม่มีโมเดล
    ({"LLM_PROVIDER": "anthropic", "OPENAI_API_KEY": KEY, "LLM_MODEL": "m"}, None),   # คีย์ผิดผู้ให้บริการ
    ({"LLM_PROVIDER": "whatever", "ANTHROPIC_API_KEY": KEY, "LLM_MODEL": "m"}, None),
    ({"LLM_PROVIDER": " Anthropic ", "ANTHROPIC_API_KEY": f" {KEY} ", "LLM_MODEL": " m "}, ("anthropic", "m")),
    ({"LLM_PROVIDER": "openai", "OPENAI_API_KEY": KEY, "LLM_MODEL": "g"}, ("openai", "g")),
])
def test_from_env(env, expect):
    c = from_env(env)
    if expect is None:
        assert c is None
    else:
        assert (c.provider, c.model) == expect and c._key == KEY


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_post_json_maps_errors(monkeypatch):
    def raiser(exc):
        def f(req, timeout=None):
            raise exc
        return f
    h = lambda code: urllib.error.HTTPError("u", code, "x", {}, io.BytesIO(b"secret body"))  # noqa: E731
    for code, retry in [(429, True), (500, True), (503, True), (400, False), (401, False), (403, False)]:
        monkeypatch.setattr(llm.urllib.request, "urlopen", raiser(h(code)))
        with pytest.raises(LLMError) as ei:
            llm._post_json("https://x", {}, {}, 1)
        assert ei.value.retryable is retry and "secret body" not in str(ei.value)
    for exc in (urllib.error.URLError("dns"), TimeoutError(), ConnectionResetError()):
        monkeypatch.setattr(llm.urllib.request, "urlopen", raiser(exc))
        with pytest.raises(LLMError) as ei:
            llm._post_json("https://x", {}, {}, 1)
        assert ei.value.retryable


def test_post_json_parses_and_rejects_bad_bodies(monkeypatch):
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda req, timeout=None: Resp(json.dumps({"a": 1}).encode()))
    assert llm._post_json("https://x", {"k": "v"}, {"b": 2}, 1) == {"a": 1}
    for raw in (b"not json", b"[1,2]", b"\xff\xfe"):
        monkeypatch.setattr(llm.urllib.request, "urlopen", lambda req, timeout=None, raw=raw: Resp(raw))
        with pytest.raises(LLMError):
            llm._post_json("https://x", {}, {}, 1)
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda req, timeout=None: Resp(b"x" * (llm.MAX_RESPONSE_BYTES + 5)))
    with pytest.raises(LLMError, match="ใหญ่"):
        llm._post_json("https://x", {}, {}, 1)


def test_post_json_sends_json_post(monkeypatch):
    seen = {}

    def fake(req, timeout=None):
        seen.update(method=req.get_method(), data=json.loads(req.data), ct=req.get_header("Content-type"), t=timeout, url=req.full_url)
        return Resp(b"{}")
    monkeypatch.setattr(llm.urllib.request, "urlopen", fake)
    llm._post_json("https://api.example/x", {"X-Key": "1"}, {"ก": "ข"}, 7)
    assert seen == {"method": "POST", "data": {"ก": "ข"}, "ct": "application/json", "t": 7, "url": "https://api.example/x"}


def test_empty_answer_error_says_why_without_leaking_content():
    c = llm.LLMClient("anthropic", "m", "k")
    data = {"content": [{"type": "thinking", "thinking": "ความลับในเนื้อหา"}], "stop_reason": "max_tokens",
            "usage": {"output_tokens": 2000}}
    with pytest.raises(llm.LLMError) as e:
        c._extract(data)
    msg = str(e.value)
    assert "stop_reason=max_tokens" in msg and "blocks=thinking" in msg and "output_tokens=2000" in msg
    assert "ความลับ" not in msg


def test_empty_openai_answer_reports_finish_reason():
    c = llm.LLMClient("openai", "m", "k")
    with pytest.raises(llm.LLMError) as e:
        c._extract({"choices": [{"message": {"content": ""}, "finish_reason": "length"}]})
    assert "finish_reason=length" in str(e.value)


# ---------- Gemini / xAI และตัวสำรอง ----------
from services.api.llm import FallbackLLM  # noqa: E402


@pytest.mark.parametrize("provider,url", [("gemini", llm.GEMINI_URL), ("xai", llm.XAI_URL)])
def test_openai_style_providers_use_their_own_endpoint(provider, url):
    calls = []
    c = LLMClient(provider, "m", KEY, post=fake_post([OPENAI_OK], calls))
    assert c.complete("SYS", "USER") == "คำตอบ"
    u, headers, body, _ = calls[0]
    assert u == url and u.startswith("https://") and headers["Authorization"] == f"Bearer {KEY}"
    assert body["messages"][0] == {"role": "system", "content": "SYS"} and body["model"] == "m"


@pytest.mark.parametrize("env,expect", [
    ({"LLM_PROVIDER": "gemini", "GEMINI_API_KEY": KEY, "LLM_MODEL": "g1"}, ("gemini", "g1")),
    ({"LLM_PROVIDER": "xai", "XAI_API_KEY": KEY, "XAI_MODEL": "x1"}, ("xai", "x1")),       # รุ่นจาก XAI_MODEL ได้
    ({"LLM_PROVIDER": "gemini", "OPENAI_API_KEY": KEY, "LLM_MODEL": "g1"}, None),           # คีย์ผิดเจ้า
])
def test_from_env_new_providers(env, expect):
    c = from_env(env)
    assert (c is None) if expect is None else ((c.provider, c.model) == expect)


BASE = {"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": KEY, "LLM_MODEL": "a1"}


def test_from_env_builds_fallback_chain_in_order_and_skips_incomplete_or_unknown():
    env = {**BASE, "LLM_FALLBACK": "gemini, nope, xai, openai, anthropic, gemini",
           "GEMINI_API_KEY": "g", "GEMINI_MODEL": "g1", "XAI_API_KEY": "x", "XAI_MODEL": "x1",
           "OPENAI_API_KEY": "o"}                     # openai ไม่มี OPENAI_MODEL จึงถูกข้าม
    c = from_env(env)
    assert isinstance(c, FallbackLLM)
    assert [(x.provider, x.model) for x in c.clients] == [("anthropic", "a1"), ("gemini", "g1"), ("xai", "x1")]
    assert (c.provider, c.model) == ("anthropic", "a1")
    assert KEY not in repr(c) and "g" not in repr(c).split("(")[0]


def test_from_env_without_usable_fallback_is_plain_client():
    assert isinstance(from_env({**BASE, "LLM_FALLBACK": "gemini"}), LLMClient)
    assert isinstance(from_env(BASE), LLMClient)


def test_fallback_tries_next_provider_when_one_fails():
    calls = []
    bad = LLMClient("anthropic", "a", KEY, retries=0, post=fake_post([LLMError("HTTP 401")], calls))
    good = LLMClient("gemini", "g", KEY, post=fake_post([OPENAI_OK], calls))
    assert FallbackLLM([bad, good]).complete("s", "u") == "คำตอบ"
    assert [c[0] for c in calls] == [llm.ANTHROPIC_URL, llm.GEMINI_URL]


def test_fallback_raises_last_error_when_all_fail():
    calls = []
    a = LLMClient("anthropic", "a", KEY, retries=0, post=fake_post([LLMError("a down")], calls))
    b = LLMClient("xai", "x", KEY, retries=0, post=fake_post([LLMError("x down")], calls))
    with pytest.raises(LLMError, match="x down"):
        FallbackLLM([a, b]).complete("s", "u")


def test_fallback_does_not_call_backup_when_main_works():
    calls = []
    a = LLMClient("anthropic", "a", KEY, post=fake_post([ANTH_OK], calls))
    b = LLMClient("gemini", "g", KEY, post=fake_post([OPENAI_OK], calls))
    assert FallbackLLM([a, b]).complete("s", "u") == "สวัสดี ครับ" and len(calls) == 1
