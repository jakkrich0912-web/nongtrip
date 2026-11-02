import json

import pytest

from services.places import knowledge as k

TODAY = "2026-11-05"


def place(pid="p01", th="วัดพระธาตุดอยสุเทพ", en="Wat Phra That Doi Suthep", lat=18.8048, lon=98.9217,
          url="https://en.wikipedia.org/wiki/Wat_Phra_That_Doi_Suthep"):
    return {"id": pid, "name_th": th, "name_en": en, "lat": lat, "lon": lon, "province": "เชียงใหม่",
            "sources": [{"url": url, "title": "x", "checked_on": "2026-10-27"}]}


def page(title, extract, lat=None, lon=None, th_title=None, pid=1):
    pg = {"pageid": pid, "title": title, "extract": extract}
    if lat is not None:
        pg["coordinates"] = [{"lat": lat, "lon": lon}]
    if th_title:
        pg["langlinks"] = [{"lang": "th", "title": th_title}]
    return pg


class FakeClient:
    """คำตอบที่เตรียมไว้ต่อภาษา เรียกซ้ำได้ นับคำขอ"""

    def __init__(self, by_lang, extra=None):
        self.by_lang = by_lang
        self.calls = []
        self.extra = extra or {}

    def get_json(self, url, params=None):
        lang = url.split("//")[1].split(".")[0]
        titles = params["titles"].split("|")
        self.calls.append((lang, titles))
        have = self.by_lang.get(lang, [])
        return {"query": {"pages": [p for p in have if p["title"] in titles]
                          + [{"title": t, "missing": True} for t in titles if t not in [p["title"] for p in have]],
                          **self.extra.get(lang, {})}}


LEAD_EN = ("Wat Phra That Doi Suthep is a Theravada Buddhist temple in Chiang Mai.\n"
           "It is a sacred site to many Thai people and sits on a mountain above the city.")
LEAD_TH = "วัดพระธาตุดอยสุเทพเป็นวัดในพุทธศาสนานิกายเถรวาท ตั้งอยู่บนดอยสุเทพ จังหวัดเชียงใหม่ เป็นปูชนียสถานสำคัญ"


# ---------- ข้อความ ----------

def test_clean_drops_forbidden_paragraphs_and_reference_marks():
    text = ("วัดนี้สร้างเมื่อปี 1383[1] เป็นวัดสำคัญของจังหวัด\n"
            "ค่าเข้าชมคนต่างชาติ 30 บาท เปิดทุกวัน\n"
            "The temple is rated five stars by many visitors online.\n"
            "Tickets can be booked at the gate every day.\n"
            "สั้น\n"
            "Located on Doi Suthep it overlooks the city of Chiang Mai from the west.")
    paras, dropped = k.clean_paragraphs(text)
    assert paras == ["วัดนี้สร้างเมื่อปี 1383 เป็นวัดสำคัญของจังหวัด",
                     "Located on Doi Suthep it overlooks the city of Chiang Mai from the west."]
    assert dropped == 3


@pytest.mark.parametrize("bad", ["ราคา 100", "ดูรีวิวได้ที่เว็บ", "จองที่พักล่วงหน้า", "คะแนน 4.5", "5 ดาว", "ชำระเงินที่หน้างาน",
                                 "Admission is free", "Entrance fee 50", "A 4.5 rating", "Reviews are mixed", "THB 100", "฿100"])
def test_forbidden_words_caught(bad):
    assert k.FORBIDDEN.search(bad)


@pytest.mark.parametrize("ok", ["ดาวเหนือส่องสว่างเหนือยอดดอย", "The feet of the mountain", "Buddhist temple in Chiang Mai"])
def test_forbidden_does_not_overreach(ok):
    assert not k.FORBIDDEN.search(ok)


def test_chunking_respects_limit_and_count():
    paras = ["ก" * 700, "ข" * 700, "ค" * 700, "ง" * 700]
    chunks = k.chunk_paragraphs(paras, limit=1200, max_chunks=2)
    assert len(chunks) == 2
    assert all(len(c) <= 1200 for c in chunks)
    assert chunks[0] == "ก" * 700 and chunks[1] == "ข" * 700


def test_chunking_packs_short_paragraphs_and_cuts_long_one():
    chunks = k.chunk_paragraphs(["a" * 30, "b" * 30], limit=1200)
    assert chunks == ["a" * 30 + "\n" + "b" * 30]
    long = k.chunk_paragraphs(["One sentence here. " * 100], limit=100)
    assert len(long) == 1 and len(long[0]) <= 100 and long[0].endswith(".")
    assert k.chunk_paragraphs([]) == []


# ---------- ที่มา ----------

def test_parse_wiki_url():
    assert k.parse_wiki_url("https://en.wikipedia.org/wiki/Wat_Phra_That_Doi_Suthep") == ("en", "Wat Phra That Doi Suthep")
    assert k.parse_wiki_url("https://th.wikipedia.org/wiki/%E0%B8%A7%E0%B8%B1%E0%B8%94") == ("th", "วัด")
    assert k.parse_wiki_url("https://example.com/wiki/X") is None
    assert k.parse_wiki_url("https://en.wikipedia.org/w/index.php?title=X") is None
    assert k.parse_wiki_url("") is None


def test_wiki_url_roundtrip():
    u = k.wiki_url("th", "วัดพระธาตุ (เชียงใหม่)")
    assert k.parse_wiki_url(u) == ("th", "วัดพระธาตุ (เชียงใหม่)")


def test_name_matches():
    names = ["วัดพระธาตุดอยสุเทพ", "Wat Phra That Doi Suthep"]
    assert k.name_matches(names, "Wat Phra That Doi Suthep")
    assert k.name_matches(names, "วัดพระธาตุดอยสุเทพ ราชวรวิหาร".replace(" ราชวรวิหาร", ""))
    assert k.name_matches(["Chiang Mai Night Bazaar"], "Night Bazaar (Chiang Mai)") is True   # ตัดวงเล็บแล้วอยู่ในชื่อสถานที่
    assert k.name_matches(["วัดเจดีย์หลวง"], "เจดีย์หลวง") is True   # ชื่อบทความอยู่ในชื่อสถานที่
    assert not k.name_matches(["วัดพระธาตุดอยสุเทพ", "Wat Phra That Doi Suthep"], "Wat Chedi Luang")
    assert not k.name_matches([None, ""], "Anything")


def test_coords_ok():
    p = place()
    assert k.coords_ok(p, {"lat": 18.8050, "lon": 98.9220}) is True
    assert k.coords_ok(p, {"lat": 18.7883, "lon": 98.9853}) is False   # ในเมืองเชียงใหม่ ห่างหลายกม.
    assert k.coords_ok(p, {"lat": None, "lon": None}) is None


# ---------- MediaWiki ----------

def test_parse_pages_follows_normalization_and_redirects():
    resp = {"query": {"normalized": [{"from": "wat x", "to": "Wat x"}], "redirects": [{"from": "Wat x", "to": "Wat X"}],
                      "pages": [page("Wat X", "text " * 10, 1.0, 2.0, th_title="วัด เอ็กซ์"),
                                {"title": "Gone", "missing": True}]}}
    out = k.parse_pages(resp, ["wat x", "Gone", "Other"])
    assert out["wat x"]["title"] == "Wat X"
    assert out["wat x"]["lat"] == 1.0 and out["wat x"]["th_title"] == "วัด เอ็กซ์"
    assert "Gone" not in out and "Other" not in out


def test_fetch_pages_batches_by_twenty():
    titles = [f"T{i}" for i in range(45)]
    client = FakeClient({"en": [page(t, "x" * 40) for t in titles]})
    naps = []
    out = k.fetch_pages(client, "en", titles, pause=1.5, sleep=naps.append)
    assert [len(c[1]) for c in client.calls] == [20, 20, 5]
    assert len(out) == 45 and naps == [1.5, 1.5]


def test_api_params_asks_thai_langlink_only_for_non_thai():
    assert k.api_params("en", ["A"])["lllang"] == "th"
    assert "lllang" not in k.api_params("th", ["A"])
    assert k.api_params("en", ["A", "B"])["titles"] == "A|B"


# ---------- สร้างคลังของหนึ่งจังหวัด ----------

def run(places, by_lang, **kw):
    return k.build_province(FakeClient(by_lang), places, TODAY, sleep=lambda s: None, **kw)


def test_prefers_thai_edition_via_langlink():
    p = place()
    docs, rep = run([p], {"en": [page("Wat Phra That Doi Suthep", LEAD_EN, 18.8048, 98.9217, th_title="วัดพระธาตุดอยสุเทพ")],
                          "th": [page("วัดพระธาตุดอยสุเทพ", LEAD_TH, 18.8049, 98.9216, pid=2)]})
    assert rep["counts"]["ok"] == 1 and rep["counts"]["th"] == 1
    assert [d["lang"] for d in docs] == ["th"]
    d = docs[0]
    assert d["id"] == "k:p01:0" and d["place_id"] == "v:p01" and d["license"] == "CC BY-SA 4.0"
    assert d["url"].startswith("https://th.wikipedia.org/wiki/") and d["checked_on"] == TODAY
    assert k.validate(docs, {"v:p01"}) == []


def test_falls_back_to_source_language_when_no_thai():
    docs, rep = run([place()], {"en": [page("Wat Phra That Doi Suthep", LEAD_EN, 18.8048, 98.9217)]})
    assert rep["counts"]["en"] == 1 and docs[0]["lang"] == "en"
    assert "Theravada" in docs[0]["text"]


def test_thai_page_without_usable_text_falls_back_to_english():
    docs, rep = run([place()], {"en": [page("Wat Phra That Doi Suthep", LEAD_EN, th_title="วัดพระธาตุดอยสุเทพ")],
                                "th": [page("วัดพระธาตุดอยสุเทพ", "ค่าเข้าชมคนต่างชาติ 30 บาท เปิดทุกวัน\nราคาตั๋วผู้ใหญ่ 20 บาท เด็กเข้าฟรี", pid=2)]})
    assert [d["lang"] for d in docs] == ["en"]
    assert rep["dropped_paragraphs"] == 2


def test_missing_page_and_non_wikipedia_source():
    p1 = place("p01")
    p2 = place("p02", url="https://example.com/x")
    docs, rep = run([p1, p2], {"en": []})
    assert docs == [] and rep["counts"]["no_page"] == 2


def test_all_text_forbidden_counts_as_no_text():
    docs, rep = run([place()], {"en": [page("Wat Phra That Doi Suthep", "Admission is 30 baht per person for foreigners.", 18.8, 98.92)]})
    assert docs == [] and rep["counts"]["no_text"] == 1 and rep["dropped_paragraphs"] == 1


def test_far_coordinates_rejected():
    docs, rep = run([place()], {"en": [page("Wat Phra That Doi Suthep", LEAD_EN, 18.7883, 98.9853)]})
    assert docs == [] and rep["counts"]["far"] == 1 and rep["far"][0][0] == "p01"


def test_name_mismatch_without_coords_goes_to_review_and_is_skipped():
    p = place(url="https://en.wikipedia.org/wiki/Chiang_Mai")
    by = {"en": [page("Chiang Mai", LEAD_EN)]}
    docs, rep = run([p], by)
    assert docs == [] and rep["counts"]["review"] == 1 and rep["review"][0][2] == "Chiang Mai"
    docs, rep = run([p], by, include_review=True)
    assert len(docs) >= 1


def test_name_mismatch_with_matching_coords_is_kept_but_flagged():
    p = place(url="https://en.wikipedia.org/wiki/Mount_Suthep")
    docs, rep = run([p], {"en": [page("Mount Suthep", LEAD_EN, 18.8049, 98.9216)]})
    assert len(docs) >= 1 and rep["name_check"] and not rep["review"]


# ---------- ไฟล์และการตรวจ ----------

def test_write_and_load_roundtrip(tmp_path):
    docs, _ = run([place()], {"en": [page("Wat Phra That Doi Suthep", LEAD_EN, 18.8048, 98.9217)]})
    path = k.write_province(tmp_path, "เชียงใหม่", docs, TODAY)
    assert path.name == "เชียงใหม่.json"
    meta = json.loads(path.read_text(encoding="utf-8"))["_meta"]
    assert meta["count"] == len(docs) and meta["province"] == "เชียงใหม่"
    assert k.load_all(tmp_path) == docs
    assert k.load_all(tmp_path / "ไม่มี") == []


def good():
    return {"id": "k:p01:0", "place_id": "v:p01", "title": "T", "text": "ข้อความที่ใช้ได้ " * 5, "url": k.wiki_url("th", "T"),
            "lang": "th", "license": "CC BY-SA 4.0", "checked_on": TODAY}


def test_validate_accepts_good_and_catches_each_rule():
    known = {"v:p01"}
    assert k.validate([good()], known) == []
    cases = {
        "ขาดฟิลด์": {**good(), "text": ""},
        "place_id": {**good(), "place_id": "v:p99"},
        "เกิน": {**good(), "text": "ก" * 1201},
        "คำต้องห้าม": {**good(), "text": "ราคาตั๋ว 100 บาท"},
        "สัญญาอนุญาต": {**good(), "license": "MIT"},
        "url": {**good(), "url": "https://example.com/a"},
    }
    for needle, bad in cases.items():
        probs = k.validate([bad], known)
        assert any(needle in p for p in probs), (needle, probs)
    dup = k.validate([good(), good()], known)
    assert any("ซ้ำ" in p for p in dup)


def test_real_data_loads_and_all_places_have_wikipedia_source():
    """ข้อมูลจริงใน repo: สถานที่ที่ตรวจแล้วทุกแห่งต้องมีที่มาเป็นบทความ Wikipedia ไม่งั้นสคริปต์สร้างคลังจะข้ามไป"""
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("bk", Path(__file__).parents[3] / "scripts" / "build_knowledge.py")
    bk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bk)
    by = bk.verified_by_province()
    places = [p for ps in by.values() for p in ps]
    assert len(places) > 300
    without = [p["id"] for p in places if not any(k.parse_wiki_url(s.get("url", "")) for s in p.get("sources") or [])]
    assert without == []
