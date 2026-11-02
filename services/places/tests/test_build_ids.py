"""รหัสสถานที่ต้องไม่เลื่อนเมื่อรัน scripts/build_places.py ใหม่ (สถานที่โปรดและคลังความรู้อ้างรหัสนี้)"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "services" / "places")]

from build_places import keep_ids  # noqa: E402
from provinces import PROVINCES  # noqa: E402

PROV = "ฉะเชิงเทรา"
IDX = PROVINCES.index(PROV) + 1


def place(pid, url, th=False):
    p = {"id": pid, "province": PROV, "name_th": url, "sources": [{"url": url}]}
    if th:
        p["matched_from_seed"] = "th-wiki"
    return p


def test_existing_place_keeps_id_when_new_title_added_before_it():
    previous = [place(f"p{IDX}01", "u/a"), place(f"p{IDX}02", "u/b")]
    # รันใหม่: มีบทความใหม่ (u/new) ถูกดึงได้ก่อน ทำให้ตัวนับเดิมเลื่อน
    rebuilt = [place(f"p{IDX}01", "u/new"), place(f"p{IDX}02", "u/a"), place(f"p{IDX}03", "u/b")]
    got = {p["sources"][0]["url"]: p["id"] for p in keep_ids(rebuilt, previous)}
    assert got["u/a"] == f"p{IDX}01"
    assert got["u/b"] == f"p{IDX}02"
    assert got["u/new"] == f"p{IDX}03"


def test_ids_of_removed_places_are_not_reused():
    previous = [place(f"p{IDX}01", "u/a"), place(f"p{IDX}02", "u/gone")]
    rebuilt = [place(f"p{IDX}01", "u/a"), place(f"p{IDX}02", "u/new")]
    got = {p["sources"][0]["url"]: p["id"] for p in keep_ids(rebuilt, previous)}
    assert got["u/new"] == f"p{IDX}03"


def test_th_wiki_places_use_41_range_and_ids_unique():
    previous = [place(f"p{IDX}41", "u/th1", th=True)]
    rebuilt = [place("x", "u/th2", th=True), place("y", "u/th1", th=True), place("z", "u/seed")]
    out = keep_ids(rebuilt, previous)
    got = {p["sources"][0]["url"]: p["id"] for p in out}
    assert got["u/th1"] == f"p{IDX}41"
    assert got["u/th2"] == f"p{IDX}42"
    assert got["u/seed"] == f"p{IDX}01"
    assert len({p["id"] for p in out}) == len(out)


def test_first_build_without_previous_file():
    out = keep_ids([place("a", "u/a"), place("b", "u/b")], [])
    assert [p["id"] for p in out] == [f"p{IDX}01", f"p{IDX}02"]


def test_places_not_found_again_are_kept_with_same_id():
    from build_places import keep_previous
    previous = [place(f"p{IDX}01", "u/a"), place(f"p{IDX}41", "u/th-lost", th=True)]
    rebuilt = keep_ids([place("x", "u/a")], previous)
    merged, kept = keep_previous(rebuilt, previous)
    assert {p["id"] for p in merged} == {f"p{IDX}01", f"p{IDX}41"}
    assert [p["id"] for p in kept] == [f"p{IDX}41"]


def test_dropped_places_are_not_kept():
    import build_places
    from build_places import keep_previous
    previous = [{**place(f"p{IDX}41", "u/bad", th=True), "name_th": "ผิดจังหวัด"}]
    build_places.DROP.add((PROV, "ผิดจังหวัด"))
    try:
        merged, kept = keep_previous([], previous)
        assert merged == [] and kept == []
    finally:
        build_places.DROP.discard((PROV, "ผิดจังหวัด"))


def test_old_id_not_given_to_same_article_found_in_another_province():
    other = "นครพนม"
    oidx = PROVINCES.index(other) + 1
    previous = [place(f"p{IDX}42", "u/park", th=True)]
    found_elsewhere = [{**place("x", "u/park", th=True), "province": other}]
    out = keep_ids(found_elsewhere, previous)
    assert out[0]["id"].startswith(f"p{oidx}")
    assert out[0]["id"] != f"p{IDX}42"


def test_new_place_with_same_name_in_same_province_is_skipped():
    previous = [{**place(f"p{IDX}01", "u/en"), "name_th": "วัดซ้ำ"}]
    rebuilt = [{**place("x", "u/en"), "name_th": "วัดซ้ำ"}, {**place("y", "u/th", th=True), "name_th": "วัดซ้ำ"}]
    out = keep_ids(rebuilt, previous)
    assert [p["id"] for p in out] == [f"p{IDX}01"]
