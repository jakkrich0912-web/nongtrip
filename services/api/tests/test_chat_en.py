"""แชตเข้าใจคำถามภาษาอังกฤษ และตอบเป็นอังกฤษครบ (ชื่อจังหวัด หมายเหตุ)"""
import pytest

from services.api.chat import _note_en
from services.api.chat_rules import parse
from services.api.tests.test_chat import _snap_client, ask, events, text_of
from services.places.provinces import PROVINCES, PROVINCES_EN, province_en


def test_every_province_has_unique_english_name():
    assert set(PROVINCES_EN) == set(PROVINCES) and len(PROVINCES_EN) == 77
    assert len({v.lower() for v in PROVINCES_EN.values()}) == 77
    assert province_en("เชียงใหม่") == "Chiang Mai" and province_en("ไม่มี") == "ไม่มี"


@pytest.mark.parametrize("th", PROVINCES)
def test_every_english_province_name_is_understood(th):
    en = PROVINCES_EN[th]
    # "Nan" ต้องมีคำนำหน้า (ไม่งั้นเป็นขนมปัง)
    assert parse(f"attractions in {en}").province == th
    assert parse(f"cafes in {en.lower().replace(' ', '')}").province == th      # พิมพ์ติดกัน เช่น chonburi


def test_english_variants_and_ambiguous_words():
    assert parse("coffee in chon-buri").province == "ชลบุรี"
    assert parse("temples in Korat").province == "นครราชสีมา"
    assert parse("hotels in Krung Thep").province == "กรุงเทพมหานคร"
    assert parse("I want some nan bread").province is None            # "nan" ไม่ใช่จังหวัดถ้าไม่มีคำนำหน้า
    assert parse("things to do in Nan province").province == "น่าน"
    assert parse("take me to the mountains").province is None          # "tak" อยู่ในคำอื่นไม่นับ


@pytest.mark.parametrize("text,kinds", [
    ("Which cafés are near my stay?", ("cafe",)),
    ("coffee shops in Phuket", ("cafe",)),
    ("temples and waterfalls near Chiang Mai", ("attraction",)),
    ("things to do in Krabi", ("attraction",)),
    ("cafes and attractions in Krabi", ("attraction", "cafe")),
])
def test_english_kinds(text, kinds):
    assert parse(text).kinds == kinds


def test_english_lodging_words_need_whole_words():
    assert parse("stays around Phuket").want_lodgings
    assert parse("hotels nearby").want_lodgings
    it = parse("a village with a temple")
    assert not it.want_lodgings and it.kinds == ("attraction",)       # "village" ไม่ใช่ "villa"


def test_english_lodging_name_query():
    assert parse("attractions near Sunshine Hotel").lodging_query == "Sunshine Hotel"
    assert parse("cafes around hotel Sunshine").lodging_query == "hotel Sunshine"
    assert parse("stays near Dusit Thani Hotel").lodging_query == "Dusit Thani Hotel"
    assert parse("hotels near me").lodging_query is None
    assert parse("best hotel in town").lodging_query is None


def test_english_limit_radius_and_topics():
    it = parse("show 7 places within 12 km")
    assert it.limit == 7 and it.radius_km == 12
    assert parse("3 cafes in Phuket").limit == 3
    assert parse("within 50 kilometers").radius_km == 30 and parse("within 50 kilometers").notes
    assert parse("how much is the ticket?").asks_money
    assert parse("any good reviews or ratings?").asks_review
    assert parse("can I book a room?").asks_booking
    assert parse("what can you do?").greeting and parse("hi").greeting and parse("Hello!").greeting
    assert not parse("hi cafes in Phuket").greeting
    assert not parse("top 5 cafes").asks_review


def test_english_question_gets_english_reply_with_english_province(tmp_path):
    c = _snap_client(tmp_path)
    evs = events(ask(c, "Attractions in Chiang Mai", lang="en"))
    out = text_of(evs)
    assert "the centre of Chiang Mai" in out and "เชียงใหม่" not in out and "Snapshot Temple" in out
    assert evs[0] == ("tool", {"name": "province_center", "args": {"province": "เชียงใหม่"}})
    assert evs[-1][1]["province"] == "เชียงใหม่"                       # บอกหน้าเว็บให้จำเป็นชื่อไทยเสมอ


def test_english_text_works_even_when_ui_is_thai(tmp_path):
    out = text_of(events(ask(_snap_client(tmp_path), "cafes in Chiang Mai")))
    assert "จุดกลางจังหวัดเชียงใหม่" in out


@pytest.mark.parametrize("thai,english", [
    ("พบหลายรายการ กรุณาเลือกที่พักที่ตรงกับที่จอง", "Several stays match"),
    ("ไม่พบที่พักชื่อนี้ ลองพิมพ์ชื่ออื่น หรือปักหมุดบนแผนที่", "No stay with this name"),
    ("แสดงผลในรัศมี 12.5 กม. เท่านั้น", "Results are shown within 12.5 km only."),
    ("ไม่พบที่พักในรัศมี 5 กม. จึงขยายเป็น 10 กม.", "widened to 10 km"),
    ("ไม่พบที่พักในรัศมี 5 กม. จากหมุดนี้", "within 5 km of this pin"),
    ("พบที่พัก 40 แห่ง แสดง 20 แห่งที่ใกล้หมุดที่สุด", "Found 40 stays; showing the 20 nearest"),
    ("พื้นที่หนาแน่นมาก ข้อมูลจาก OpenStreetMap จึงครอบคลุมแค่ 8 กม.", "covers only 8 km"),
    ("เชื่อมต่อ OpenStreetMap ไม่ได้ในตอนนี้ แสดงเฉพาะสถานที่ที่ตรวจที่มาแล้ว", "Cannot reach OpenStreetMap right now."),
    ("ค้นชื่อที่พักออนไลน์ไม่ได้ในตอนนี้ ให้ปักหมุดบนแผนที่แทน", "pin your stay on the map instead"),
    ("ระบบตรวจคำตอบอัตโนมัติไม่ผ่าน จึงแสดงผลแบบพื้นฐานแทน", "automatic answer check failed"),
])
def test_service_notices_are_translated(thai, english):
    out = _note_en(thai)
    assert english in out and not any("฀" <= ch <= "๿" for ch in out)


def test_unknown_notice_is_left_as_is():
    assert _note_en("ข้อความที่ไม่รู้จัก") == "ข้อความที่ไม่รู้จัก"
