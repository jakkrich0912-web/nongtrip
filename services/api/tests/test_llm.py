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
