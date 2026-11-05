"""แชตแบบแอปแชตทั่วไป: รหัสข้อความใน done, 👍👎, เปลี่ยนชื่อแชต, แก้คำถาม/ถามใหม่ และเก็บการ์ดไว้กับคำตอบ"""
from services.api.store import MAX_EXTRA_BYTES, Store
from services.api.tests.test_chat import LAT, LON, events, make

PW = "รหัสผ่านยาวพอ-123"


def login(c, email="x@example.com"):
    assert c.post("/api/auth/register", json={"email": email, "password": PW}).status_code == 201


def ask(c, msg, **kw):
    evs = events(c.post("/api/chat", json={"message": msg, **kw}))
    assert evs[-1][0] == "done"
    return evs


def test_done_has_message_ids_only_when_logged_in(tmp_path):
    c, *_ = make(tmp_path)
    done = ask(c, "ขอบคุณ")[-1][1]
    assert "message_id" not in done and "user_message_id" not in done
    login(c)
    done = ask(c, "ขอบคุณ")[-1][1]
    assert done["message_id"] > done["user_message_id"] > 0
    chat = c.get(f"/api/me/chats/{done['chat_id']}").json()
    assert [(m["id"], m["role"]) for m in chat["messages"]] == [(done["user_message_id"], "user"), (done["message_id"], "assistant")]
    assert chat["messages"][1]["extra"]["mode"] == "rule" and chat["messages"][1]["rating"] is None


def test_places_cards_are_saved_with_the_answer(tmp_path):
    c, *_ = make(tmp_path)
    login(c)
    evs = ask(c, "คาเฟ่ใกล้ๆ", context={"lat": LAT, "lon": LON})
    sent = next(d for e, d in evs if e == "places")
    chat = c.get(f"/api/me/chats/{evs[-1][1]['chat_id']}").json()
    assert chat["messages"][1]["extra"]["places"]["items"] == sent["items"]


def test_rating_thumbs_up_down_and_clear(tmp_path):
    c, *_ = make(tmp_path)
    login(c)
    done = ask(c, "ขอบคุณ")[-1][1]
    url = f"/api/me/chats/{done['chat_id']}/messages/{done['message_id']}/rating"
    assert c.put(url, json={"rating": 1}).json() == {"message_id": done["message_id"], "rating": 1}
    assert c.get(f"/api/me/chats/{done['chat_id']}").json()["messages"][1]["rating"] == 1
    c.put(url, json={"rating": -1})
    assert c.get(f"/api/me/chats/{done['chat_id']}").json()["messages"][1]["rating"] == -1
    c.put(url, json={"rating": 0})
    assert c.get(f"/api/me/chats/{done['chat_id']}").json()["messages"][1]["rating"] is None
    assert c.put(url, json={"rating": 5}).status_code == 400
    # ให้คะแนนข้อความของผู้ใช้เองไม่ได้
    assert c.put(f"/api/me/chats/{done['chat_id']}/messages/{done['user_message_id']}/rating", json={"rating": 1}).status_code == 404


def test_cannot_touch_other_users_chat(tmp_path):
    c, *_ = make(tmp_path)
    login(c, "a@example.com")
    done = ask(c, "ขอบคุณ")[-1][1]
    c.post("/api/auth/logout")
    c.cookies.clear()
    login(c, "b@example.com")
    cid, mid = done["chat_id"], done["message_id"]
    assert c.put(f"/api/me/chats/{cid}/messages/{mid}/rating", json={"rating": 1}).status_code == 404
    assert c.patch(f"/api/me/chats/{cid}", json={"title": "ของฉันแล้ว"}).status_code == 404
    r = c.post("/api/chat", json={"message": "สวัสดี", "chat_id": cid, "edit_from": done["user_message_id"]})
    assert r.status_code == 404


def test_rename_chat(tmp_path):
    c, *_ = make(tmp_path)
    login(c)
    cid = ask(c, "ขอบคุณ")[-1][1]["chat_id"]
    assert c.patch(f"/api/me/chats/{cid}", json={"title": "  ทริป   น่าน  "}).json() == {"id": cid, "title": "ทริป น่าน"}
    assert c.get("/api/me/chats").json()["items"][0]["title"] == "ทริป น่าน"
    assert c.patch(f"/api/me/chats/{cid}", json={"title": "   "}).status_code == 400
    assert c.patch(f"/api/me/chats/{cid}", json={"title": "ก" * 81}).status_code == 400
    assert c.patch("/api/me/chats/999", json={"title": "x"}).status_code == 404


def test_edit_question_replaces_it_and_everything_after(tmp_path):
    c, *_ = make(tmp_path)
    login(c)
    first = ask(c, "ขอบคุณ")[-1][1]
    cid = first["chat_id"]
    second = ask(c, "สวัสดี", chat_id=cid)[-1][1]
    # แก้คำถามแรก: คำถามแรก คำตอบแรก และคู่ที่สองหายไป เหลือคำถามใหม่กับคำตอบใหม่
    third = ask(c, "ชื่ออะไร", chat_id=cid, edit_from=first["user_message_id"])[-1][1]
    msgs = c.get(f"/api/me/chats/{cid}").json()["messages"]
    assert [m["content"] for m in msgs if m["role"] == "user"] == ["ชื่ออะไร"]
    assert len(msgs) == 2 and msgs[0]["id"] == third["user_message_id"]
    assert second["message_id"] not in {m["id"] for m in msgs}


def test_edit_from_must_be_a_user_message_of_that_chat(tmp_path):
    c, *_ = make(tmp_path)
    login(c)
    done = ask(c, "ขอบคุณ")[-1][1]
    r = c.post("/api/chat", json={"message": "สวัสดี", "chat_id": done["chat_id"], "edit_from": done["message_id"]})
    assert r.status_code == 404                     # รหัสคำตอบของน้องทริป ไม่ใช่คำถาม
    assert len(c.get(f"/api/me/chats/{done['chat_id']}").json()["messages"]) == 2


def test_oversized_extra_keeps_only_mode_and_sources(tmp_path):
    s = Store(tmp_path / "t.db")
    from services.api import auth
    u = s.create_user("z@example.com", auth.hash_password(PW))
    cid = s.create_chat(u["id"], "x")
    big = {"mode": "llm", "sources": {"items": []}, "places": {"items": [{"n": "ก" * 1000}] * (MAX_EXTRA_BYTES // 500)}}
    s.add_message(u["id"], cid, "assistant", "ตอบ", big)
    assert s.get_chat(u["id"], cid)["messages"][0]["extra"] == {"mode": "llm", "sources": {"items": []}}


def test_old_database_gets_new_columns(tmp_path):
    import sqlite3
    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.executescript("""CREATE TABLE chat_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL,
        role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL);""")
    con.close()
    Store(db).list_chats(1)
    cols = {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(chat_messages)")}
    assert {"rating", "extra"} <= cols


def test_lodging_near_a_landmark_asks_for_lodgings():
    from services.api.chat_rules import parse
    assert parse("ที่พักใกล้ดอยสุเทพ").want_lodgings
    assert parse("โรงแรมแถววัดพระธาตุดอยสุเทพ").want_lodgings
    assert parse("hotels near Doi Suthep").want_lodgings
    assert not parse("ที่เที่ยวใกล้ที่พัก").want_lodgings
    assert not parse("attractions near my hotel").want_lodgings


def test_general_travel_words_are_detected_but_plain_searches_are_not():
    from services.api.chat_rules import parse
    for q in ("ไปเชียงใหม่ช่วงไหนดี", "แนะนำแผนเที่ยว 3 วันในน่าน", "เดินทางจากกรุงเทพไปเชียงใหม่ยังไง",
              "ทะเลที่ไหนสวยในไทย", "best time to visit Chiang Mai", "how to get to Chiang Mai"):
        assert parse(q).asks_general, q
    for q in ("ที่เที่ยวในเชียงใหม่ 5 แห่ง", "คาเฟ่ใกล้ๆ", "cafes in Chiang Mai", "ที่เที่ยวในเชียงราย ในระยะเส้นตรง 10 กม."):
        assert not parse(q).asks_general, q


def test_ask_location_example_fits_the_subject():
    from services.api.chat import _ask_location
    from services.api.chat_rules import parse
    assert "ทะเลในภูเก็ต" in " ".join(_ask_location(parse("ทะเลที่ไหนสวย")))
    assert "วัดในเชียงใหม่" in " ".join(_ask_location(parse("อยากไปวัด")))
