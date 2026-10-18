"""เทส roster_to_report — รูปร่างข้อมูลที่หน้าเว็บอ่าน

ผู้ใช้เลือกให้รายงานแสดงชื่อสมาชิกโครงงานด้วย (2026-10-18) เทสชุดนี้จึงคุมว่า members
ถูกส่งออกไปครบและอยู่ในรูปแบบที่หน้าเว็บแสดงได้ ไม่ใช่คุมว่าต้องไม่มี
"""
import copy
import json

import pytest

from sync.report_shape import roster_to_report


def row(room, grade, *, teacher="ครูเอ", plan="", code="", subject="", projects=()):
    return {
        "room": room, "grade": grade, "plan": plan, "course_code": code,
        "subject": subject, "teacher": teacher, "projects": list(projects),
    }


def proj(name, members, advisor="ครูเอ"):
    return {"name": name, "members": list(members), "advisor": advisor}


# --- รายชื่อสมาชิก -----------------------------------------------------------
def test_ส่งรายชื่อสมาชิกออกไปครบ():
    roster = [row("ม.1/1", "ม.1", projects=[proj("ก", ["เด็กชายสมชาย ใจดี", "เด็กหญิงมาลี รักเรียน"])])]
    out = roster_to_report(roster)["rooms"][0]["projects"][0]
    assert out["members"] == "เด็กชายสมชาย ใจดี, เด็กหญิงมาลี รักเรียน"
    assert out["member_count"] == 2


def test_members_เป็นสตริงไม่ใช่ลิสต์():
    """หน้าเว็บแสดงค่านี้ตรง ๆ ({p.members}) ถ้าเป็นลิสต์จะขึ้นติดกันไม่มีตัวคั่น"""
    roster = [row("ม.1/1", "ม.1", projects=[proj("ก", ["a", "b"])])]
    assert isinstance(roster_to_report(roster)["rooms"][0]["projects"][0]["members"], str)


def test_โครงงานไม่มีสมาชิกได้สตริงว่าง():
    roster = [row("ม.1/1", "ม.1", projects=[proj("ก", [])])]
    out = roster_to_report(roster)["rooms"][0]["projects"][0]
    assert out["members"] == ""
    assert out["member_count"] == 0


def test_includes_members_เป็น_true():
    assert roster_to_report([])["includes_members"] is True


# --- การยุบห้องที่มีหลายแถว ---------------------------------------------------
def test_ห้องเดียวแยกสองรายวิชา_ยุบเหลือรายการเดียว():
    """ม.1/8 แยกดนตรีไทย/ดนตรีสากล เป็น 2 แถวใน roster คนละครู ต้องเหลือ 1 ห้อง"""
    roster = [
        row("ม.1/8", "ม.1", teacher="ครูเอ", code="ว20211", subject="ดนตรีไทย"),
        row("ม.1/8", "ม.1", teacher="ครูบี", code="ว20212", subject="ดนตรีสากล",
            projects=[proj("ก", ["x"]), proj("ข", ["y", "z"])]),
    ]
    out = roster_to_report(roster)
    assert len(out["rooms"]) == 1
    assert out["summary"]["rooms"] == 1
    assert out["rooms"][0]["teachers"] == ["ครูเอ", "ครูบี"]
    assert len(out["rooms"][0]["plans"]) == 2
    assert out["rooms"][0]["submitted"] is True
    assert [p["ord"] for p in out["rooms"][0]["projects"]] == [1, 2]


def test_plan_ซ้ำไม่เก็บสองรอบ():
    roster = [row("ม.1/1", "ม.1", code="ว1", subject="ก"), row("ม.1/1", "ม.1", code="ว1", subject="ก")]
    assert len(roster_to_report(roster)["rooms"][0]["plans"]) == 1


def test_ครูชื่อว่างไม่ถูกนับ():
    out = roster_to_report([row("ม.3/1", "ม.3", teacher="")])
    assert out["rooms"][0]["teachers"] == []
    assert out["summary"]["teachers"] == 0


def test_ครูคนเดียวสอนหลายห้องนับครั้งเดียว():
    roster = [row("ม.1/1", "ม.1", teacher="ครูเอ"), row("ม.1/2", "ม.1", teacher="ครูเอ")]
    assert roster_to_report(roster)["summary"]["teachers"] == 1


# --- การเรียงลำดับ ------------------------------------------------------------
def test_เรียงห้องตามเลขไม่ใช่ตามตัวอักษร():
    roster = [row("ม.2/10", "ม.2"), row("ม.2/9", "ม.2"), row("ม.2/1", "ม.2")]
    assert [r["room"] for r in roster_to_report(roster)["rooms"]] == ["ม.2/1", "ม.2/9", "ม.2/10"]


def test_เรียงชั้นตามเลข():
    roster = [row("ม.4/1", "ม.4"), row("ม.1/1", "ม.1"), row("ม.6/1", "ม.6")]
    out = roster_to_report(roster)
    assert [g["grade"] for g in out["grades"]] == ["ม.1", "ม.4", "ม.6"]
    assert [r["room"] for r in out["rooms"]] == ["ม.1/1", "ม.4/1", "ม.6/1"]


@pytest.mark.parametrize("room", ["ไม่มีเลข", "ม.1", "/", ""])
def test_ชื่อห้องแปลก_ไม่พัง(room):
    assert roster_to_report([row(room, "ม.1")])["summary"]["rooms"] == 1


# --- ตัวเลขสรุป --------------------------------------------------------------
def test_ยอดสรุปตรง():
    roster = [
        row("ม.1/1", "ม.1", teacher="ครูเอ", projects=[proj("ก", ["a", "b"])]),
        row("ม.1/2", "ม.1", teacher="ครูบี"),
        row("ม.2/1", "ม.2", teacher="ครูซี", projects=[proj("ข", ["c"]), proj("ค", ["d", "e"])]),
    ]
    assert roster_to_report(roster)["summary"] == {
        "rooms": 3, "submitted": 2, "projects": 3, "students": 5,
        "teachers": 3, "last_synced_at": None,
    }


def test_grades_นับแยกชั้นถูก():
    roster = [
        row("ม.1/1", "ม.1", projects=[proj("ก", ["a"])]),
        row("ม.1/2", "ม.1"),
        row("ม.2/1", "ม.2", projects=[proj("ข", ["b"])]),
    ]
    assert roster_to_report(roster)["grades"] == [
        {"grade": "ม.1", "rooms": 2, "submitted": 1, "projects": 1},
        {"grade": "ม.2", "rooms": 1, "submitted": 1, "projects": 1},
    ]


def test_last_synced_at_ส่งผ่านตรงๆ():
    out = roster_to_report([], last_synced_at="2026-10-18T09:00:00Z")
    assert out["summary"]["last_synced_at"] == "2026-10-18T09:00:00Z"


# --- ความปลอดภัยของ input/output ---------------------------------------------
def test_roster_ว่างไม่พัง():
    assert roster_to_report([]) == {
        "summary": {"rooms": 0, "submitted": 0, "projects": 0, "students": 0,
                    "teachers": 0, "last_synced_at": None},
        "grades": [], "rooms": [], "includes_members": True,
    }


def test_ไม่แก้ไข_input():
    roster = [row("ม.5/1", "ม.5", projects=[proj("n", ["a"])])]
    snapshot = copy.deepcopy(roster)
    roster_to_report(roster)
    assert roster == snapshot


def test_ผลลัพธ์เขียนเป็น_json_ได้():
    roster = [row("ม.1/1", "ม.1", projects=[proj("ก", ["a"])])]
    assert json.loads(json.dumps(roster_to_report(roster), ensure_ascii=False))["rooms"]


def test_key_ที่ขาดไปใน_row_ไม่ทำให้พัง():
    """roster จาก parse_is อาจไม่มี key ครบทุกตัวถ้าไฟล์ครูผิดรูปแบบ"""
    out = roster_to_report([{"room": "ม.1/1", "grade": "ม.1"}])
    assert out["rooms"][0]["teachers"] == []
    assert out["rooms"][0]["submitted"] is False



# --- ที่ปรึกษา ----------------------------------------------------------------
def test_ที่ปรึกษาส่งออกไปตามต้นทาง():
    """เดิมเคยมีตัวกรองตัดที่ปรึกษาหลายชื่อทิ้ง ถอดออกแล้วตอนผู้ใช้เลือกเปิดเผยชื่อนักเรียน
    (2026-10-18) ค่าที่ parse ได้จึงผ่านออกไปตรง ๆ"""
    advisor = "นางสาวสุภาพร ก 2.นายกฤตภาส ข"
    roster = [row("ม.1/7", "ม.1", projects=[proj("ก", ["a"], advisor=advisor)])]
    assert roster_to_report(roster)["rooms"][0]["projects"][0]["advisor"] == advisor


def test_ไม่มีที่ปรึกษาได้สตริงว่าง():
    roster = [row("ม.1/1", "ม.1", projects=[proj("ก", ["a"], advisor="")])]
    assert roster_to_report(roster)["rooms"][0]["projects"][0]["advisor"] == ""


def test_grades_นับห้องที่ยุบแล้วไม่ใช่นับแถว():
    """ม.1/8 มี 2 แถวใน roster แต่เป็นห้องเดียว grades ต้องบอก 1 ห้อง ไม่ใช่ 2

    เทสนี้มาจากการที่เวอร์ชันร่างโดย orchestrator นับ grades ใน loop ของแถว ทำให้แถบ
    ความคืบหน้าแยกตามระดับชั้นในหน้าเว็บแสดงจำนวนห้องเกินจริง (2026-10-18)
    """
    roster = [
        row("ม.1/8", "ม.1", teacher="ครูเอ", code="ว1"),
        row("ม.1/8", "ม.1", teacher="ครูบี", code="ว2", projects=[proj("ก", ["x"])]),
    ]
    out = roster_to_report(roster)
    assert out["grades"] == [{"grade": "ม.1", "rooms": 1, "submitted": 1, "projects": 1}]
    assert out["summary"]["rooms"] == 1
