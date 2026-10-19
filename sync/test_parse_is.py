"""เทส parse_is — ตัวแกะไฟล์ที่ครูส่ง

โมดูลนี้พอร์ตมาจากโปรเจกต์เดิมเกือบทั้งดุ้นและไม่มีเทสเลย ทั้งที่เป็นจุดเดียวในสายงานที่
"ข้อมูลรูปแบบอิสระจากคนภายนอก" ไหลเข้ามา (ครูตั้งชื่อไฟล์เอง ทำตารางคนละแบบ) เทสชุดนี้คุม
2 เรื่อง: (1) กฎการแปลงข้อความที่ตัวเลขในรายงานขึ้นอยู่กับมันตรง ๆ (2) ไฟล์เดียวพัง/หาย
ต้องไม่ล้มทั้งรอบ sync

ทุก fixture สร้างขึ้นเองใน tmp_path — ห้ามแตะ Google Drive, เน็ต หรือไฟล์จริงใน data/
และชื่อคนในเทสเป็นชื่อสมมติทั้งหมด (repo นี้ public)
"""
import logging

import docx
import openpyxl
import pytest

from sync.parse_is import (
    FREEFORM_KANCHAPHORN,
    FREEFORM_M1_11,
    RosterNotFoundError,
    _lastname,
    extract_projects,
    match_projects_to_rooms,
    members,
    norm_room,
    read_desc_status,
    read_roster,
    split_glued_members,
)


# --- norm_room ---------------------------------------------------------------
@pytest.mark.parametrize("text, expected", [
    ("ม.3/7", "ม.3/7"),
    ("ม3/7", "ม.3/7"),
    ("ม. 3 / 7", "ม.3/7"),
    ("มัธยมศึกษาปีที่ 3/7", "ม.3/7"),
    ("ชั้นมัธยมศึกษาปีที่ 3/7", "ม.3/7"),
    ("ม.3 ห้อง 7", "ม.3/7"),
    ("ชั้นมัธยมศึกษาปีที่ 3 ห้อง 7", "ม.3/7"),
    ("ม.3ทับ7", "ม.3/7"),          # ชื่อไฟล์ใช้คำว่า "ทับ" แทน /
    ("ม2 ห้อง 3", "ม.2/3"),
    ("ห้อง 7", None),               # ไม่มีระดับชั้น เดาไม่ได้ว่า ม.อะไร
    ("รายละเอียดโครงงาน ชั้นมัธยมศึกษาปีที่ 5 ห้อง 12", "ม.5/12"),
])
def test_norm_room_รูปแบบที่ครูเขียนจริง(text, expected):
    assert norm_room(text) == expected


def test_norm_room_ข้อความว่างหรือ_None():
    assert norm_room("") is None
    assert norm_room(None) is None


def test_norm_room_ระดับชั้นนอกช่วง_ม1ถึงม6():
    """กันเลขปีอื่นที่หลุดมาในข้อความ (เช่น "ม.7") ไม่ให้กลายเป็นห้องเรียน"""
    assert norm_room("ม.7/1") is None
    assert norm_room("ม.0/1") is None


def test_norm_room_จุดคั่นก่อนคำว่าห้องยังไม่รองรับ():
    """ช่องว่างที่รู้อยู่: "ม.1.ห้อง 9" (มีจุดคั่นก่อน "ห้อง") ยังแปลงไม่ได้

    เทสนี้ล็อกพฤติกรรม "ปัจจุบัน" ไว้ ไม่ใช่บอกว่าถูก — ถ้าจะแก้ให้รองรับ ต้องรัน
    export เทียบ summary (51 ห้อง / 303 โครงงาน / 1249 คน) ก่อน merge เพราะกฎนี้
    มีผลต่อการจับคู่ห้องโดยตรง
    """
    assert norm_room("ม.1.ห้อง 9") is None


# --- _lastname ---------------------------------------------------------------
@pytest.mark.parametrize("teacher, expected", [
    ("นางสาวมาลี รักเรียน", "มาลี"),
    ("นางสาว มาลี รักเรียน", "มาลี"),
    ("นายสมชาย ใจดี", "สมชาย"),
    ("นางสมหญิง ใจงาม", "สมหญิง"),
    ("ครูสมปอง ขยันยิ่ง", "สมปอง"),
    ("ว่าที่ ร.ต. สมศักดิ์ มั่นคง", "สมศักดิ์"),
    ("ว่าที่ ร.ต. หญิง สมหญิง มั่นคง", "สมหญิง"),   # คำนำหน้าซ้อน 2 ชั้น
    ("", ""),
])
def test_lastname_ตัดคำนำหน้า(teacher, expected):
    assert _lastname(teacher) == expected


def test_lastname_คำนำหน้าหญิงต้องไม่เหลือคำว่าหญิงติดมา():
    """ถ้า alternation เรียงผิด "ว่าที่ ร.ต." จะ match ก่อนแล้วได้ชื่อเป็น "หญิง"
    ทุกคน — ครูกลุ่มนี้จะจับคู่ห้องมั่วทั้งหมด"""
    assert _lastname("ว่าที่ ร.ต. หญิง สมหญิง มั่นคง") != "หญิง"


# --- read_roster -------------------------------------------------------------
def write_roster_xlsx(dirpath, rows, name="รายชื่อครู_รายวิชา_IS_เทอม1.xlsx"):
    """สร้างไฟล์บัญชีจัดครูเข้าสอน: หัวตาราง 2 บรรทัด ข้อมูลเริ่มแถว 3
    คอลัมน์ A=ชั้น/ห้อง B=แผนการเรียน C=จำนวน D=รหัสวิชา E=ชื่อวิชา F=ครูผู้สอน"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["บัญชีจัดครูเข้าสอน IS เทอม 1"])
    ws.append(["ชั้น/ห้อง", "ห้องเรียน/แผนการเรียน", "จำนวน", "รหัสวิชา", "ชื่อวิชา", "ครูผู้สอน"])
    for r in rows:
        ws.append(list(r))
    path = dirpath / name
    wb.save(str(path))
    return path


def test_read_roster_แถวธรรมดา(tmp_path):
    write_roster_xlsx(tmp_path, [("ม.1/1", "ทั่วไป", 40, "I21201", "IS 1", "นายสมชาย ใจดี")])
    rows = read_roster(tmp_path)
    assert rows == [{
        "room": "ม.1/1", "grade": "ม.1", "plan": "ทั่วไป", "course_code": "I21201",
        "subject": "IS 1", "teacher": "นายสมชาย ใจดี",
    }]


def test_read_roster_คอลัมน์A_ว่างคือแผนการเรียนย่อยของห้องเดิม(tmp_path):
    """ม.1/8 แยกเป็นดนตรีไทย/ดนตรีสากล คนละครู — แถวที่ 2 คอลัมน์ A ว่าง
    ต้องยังเป็นห้อง ม.1/8 ไม่ใช่หลุดไป (หรือไปติดห้องก่อนหน้า)"""
    write_roster_xlsx(tmp_path, [
        ("ม.1/8", "ดนตรีไทย", 20, "I21201", "IS 1", "นายสมชาย ใจดี"),
        (None, "ดนตรีสากล", 18, "I21202", "IS 1", "นางสาวมาลี รักเรียน"),
    ])
    rows = read_roster(tmp_path)
    assert [(r["room"], r["plan"], r["teacher"]) for r in rows] == [
        ("ม.1/8", "ดนตรีไทย", "นายสมชาย ใจดี"),
        ("ม.1/8", "ดนตรีสากล", "นางสาวมาลี รักเรียน"),
    ]


def test_read_roster_กลุ่มย่อยรหัสวิชาเดิมไม่มีครูถูกรวมเข้าแถวก่อน(tmp_path):
    """ม.5/4 แบ่ง "ศิลป์คำนวณ" / "คอมพิวเตอร์" ใต้ I30201 เดียวกัน แถวหลังไม่มีครู
    ต้องรวมเป็นแถวเดียว ไม่ใช่ 2 แถว (ไม่งั้นจำนวนห้องในรายงานเกิน)"""
    write_roster_xlsx(tmp_path, [
        ("ม.5/4", "ศิลป์คำนวณ 1-25", 25, "I30201", "IS 1", "นายสมชาย ใจดี"),
        (None, "คอมพิวเตอร์ 26-36", 11, "I30201", "IS 1", None),
    ])
    rows = read_roster(tmp_path)
    assert len(rows) == 1
    assert rows[0]["plan"] == "ศิลป์คำนวณ 1-25 + คอมพิวเตอร์ 26-36"
    assert rows[0]["teacher"] == "นายสมชาย ใจดี"


def test_read_roster_ตัดคำต่อท้ายในวงเล็บออกจากชื่อครู(tmp_path):
    write_roster_xlsx(tmp_path, [("ม.2/3", "", 38, "I20201", "IS 1", "นางสาวมาลี รักเรียน (ปัจจุบัน)")])
    assert read_roster(tmp_path)[0]["teacher"] == "นางสาวมาลี รักเรียน"


def test_read_roster_แถวว่างและแถวคั่นถูกข้าม(tmp_path):
    write_roster_xlsx(tmp_path, [
        ("ม.1/1", "ทั่วไป", 40, "I21201", "IS 1", "นายสมชาย ใจดี"),
        (None, None, None, None, None, None),
        ("ม.1/2", "ทั่วไป", 41, "I21201", "IS 1", "นางสาวมาลี รักเรียน"),
    ])
    assert [r["room"] for r in read_roster(tmp_path)] == ["ม.1/1", "ม.1/2"]


def test_read_roster_แถวก่อนเจอห้องแรกถูกข้าม(tmp_path):
    """แถวหัวตารางที่เหลือ/ข้อความนำ ไม่ควรกลายเป็นห้องเรียน"""
    write_roster_xlsx(tmp_path, [
        (None, "ยังไม่ระบุห้อง", None, "I21201", "IS 1", "นายสมชาย ใจดี"),
        ("ม.1/1", "ทั่วไป", 40, "I21201", "IS 1", "นางสาวมาลี รักเรียน"),
    ])
    assert [r["room"] for r in read_roster(tmp_path)] == ["ม.1/1"]


def test_read_roster_ไม่มีรหัสวิชาใส่ขีด(tmp_path):
    write_roster_xlsx(tmp_path, [("ม.6/1", "ทั่วไป", 30, None, "ชุมนุม", "นายสมชาย ใจดี")])
    assert read_roster(tmp_path)[0]["course_code"] == "—"


def test_read_roster_ไม่มีไฟล์ยก_RosterNotFoundError(tmp_path):
    """ต้องเป็น RosterNotFoundError (ลูกของ RuntimeError) ไม่ใช่ SystemExit —
    ผู้เรียกถือเป็น skip ของรอบ sync ไม่ใช่ error และต้องจับได้ด้วย except Exception"""
    with pytest.raises(RosterNotFoundError):
        read_roster(tmp_path)
    assert issubclass(RosterNotFoundError, Exception)


def test_read_roster_มีไฟล์ชื่อไม่เข้าเกณฑ์ก็ยังถือว่าไม่มี(tmp_path):
    write_roster_xlsx(tmp_path, [("ม.1/1", "", 40, "I21201", "IS 1", "นายสมชาย ใจดี")],
                      name="ตารางสอนรวม.xlsx")
    with pytest.raises(RosterNotFoundError):
        read_roster(tmp_path)


# --- read_desc_status --------------------------------------------------------
IS_DATA_HTML = """<!doctype html><html><body><script>
window.IS_DATA = {"courses": [
  {"code": "I21201", "status": "ok", "name": "IS 1"},
  {"code": "I21202", "status": "variant"},
  {"code": "I21203"},
  {"code": "", "status": "mismatch"}
]};
</script></body></html>"""


def write_desc_html(dirpath, html):
    path = dirpath / "IS1_รายวิชาบูรณาการ.html"
    path.write_text(html, encoding="utf-8")
    return path


def test_read_desc_status_ไม่มีไฟล์ได้_dict_ว่าง(tmp_path):
    assert read_desc_status(tmp_path) == {}


def test_read_desc_status_อ่าน_window_IS_DATA(tmp_path):
    write_desc_html(tmp_path, IS_DATA_HTML)
    assert read_desc_status(tmp_path) == {
        "I21201": "ok",
        "I21202": "variant",
        "I21203": "ok",      # ไม่ระบุ status ถือว่า ok
    }                        # รหัสวิชาว่างถูกตัดออก


def test_read_desc_status_นับวงเล็บปีกกาซ้อนถูกต้อง(tmp_path):
    """ต้องหยุดที่ปีกกาปิดของ IS_DATA เอง ไม่ใช่ตัวแรกที่เจอ"""
    write_desc_html(tmp_path, """<script>
window.IS_DATA = {"meta": {"generated": "2026-10-18"}, "courses": [{"code": "I30201", "status": "ok"}]};
var other = {"code": "ไม่เกี่ยว", "status": "mismatch"};
</script>""")
    assert read_desc_status(tmp_path) == {"I30201": "ok"}


def test_read_desc_status_ปีกกาในสตริงไม่ทำให้นับเพี้ยน(tmp_path):
    write_desc_html(tmp_path, """<script>
window.IS_DATA = {"note": "มีปีกกา { ในข้อความ \\" และเครื่องหมายคำพูด", "courses": [{"code": "I21201", "status": "ok"}]};
</script>""")
    assert read_desc_status(tmp_path) == {"I21201": "ok"}


@pytest.mark.parametrize("html, label", [
    ("<html><body>ไม่มีอะไรเลย</body></html>", "ไม่มี window.IS_DATA"),
    ("<script>window.IS_DATA = </script>", "ไม่มี JSON ต่อท้าย"),
    ('<script>window.IS_DATA = {"courses": [{"code": }]};</script>', "JSON เสีย"),
    ('<script>window.IS_DATA = {"courses": [</script>', "ปิดวงเล็บไม่ครบ"),
    ("<script>window.IS_DATA = [1, 2, 3];</script>", "ไม่ใช่ object"),
    ("", "ไฟล์ว่าง"),
])
def test_read_desc_status_ไฟล์พังต้องไม่_throw(tmp_path, html, label):
    """ไฟล์นี้ถูก generate ขึ้นมา ถ้าพังควรแค่ไม่มีสถานะ ไม่ใช่ล้มทั้งรอบ sync"""
    write_desc_html(tmp_path, html)
    assert read_desc_status(tmp_path) == {}, label


def test_read_desc_status_courses_ไม่ใช่ลิสต์ก็ไม่_throw(tmp_path):
    write_desc_html(tmp_path, '<script>window.IS_DATA = {"courses": []};</script>')
    assert read_desc_status(tmp_path) == {}


# --- split_glued_members -----------------------------------------------------
# ชื่อสมมติทั้งหมด ห้ามใช้ชื่อนักเรียนจริงจากไฟล์ใน Drive
def test_split_glued_members_แยกรายชื่อที่ติดมากับชื่อโครงงาน():
    rec = {"projects": [{
        "name": "เครื่องรดน้ำต้นไม้อัตโนมัติ 1.ด.ช. ก กขค 2.ด.ญ. ข ขคง 3.ด.ช. ค คงจ",
        "members": [], "advisor": "นายสมชาย ใจดี",
    }]}
    split_glued_members(rec)
    p = rec["projects"][0]
    assert p["name"] == "เครื่องรดน้ำต้นไม้อัตโนมัติ"
    assert p["members"] == ["ด.ช. ก กขค", "ด.ญ. ข ขคง", "ด.ช. ค คงจ"]


def test_split_glued_members_ไม่มีรายชื่อติดมาไม่แตะต้อง():
    rec = {"projects": [{"name": "ถังขยะแยกประเภท", "members": ["เด็กชาย ก กขค"], "advisor": ""}]}
    split_glued_members(rec)
    assert rec["projects"][0] == {"name": "ถังขยะแยกประเภท", "members": ["เด็กชาย ก กขค"], "advisor": ""}


def test_split_glued_members_ไม่ทับรายชื่อเดิมที่มีมากกว่า():
    """ถ้าตารางให้รายชื่อมาครบแล้ว อย่าเอาที่แกะจากชื่อโครงงาน (ซึ่งมักขาด) ไปทับ"""
    rec = {"projects": [{
        "name": "หุ่นยนต์เก็บขยะ 1.ด.ช. ก กขค",
        "members": ["เด็กชาย ก กขค", "เด็กหญิง ข ขคง", "เด็กชาย ค คงจ"],
        "advisor": "",
    }]}
    split_glued_members(rec)
    assert rec["projects"][0]["name"] == "หุ่นยนต์เก็บขยะ"
    assert len(rec["projects"][0]["members"]) == 3


def test_split_glued_members_ชื่อโครงงานสั้นเกินไม่ตัด():
    """ถ้าหัวสั้นกว่า 5 ตัวอักษร แปลว่าแกะผิดจุด (ทั้งช่องเป็นรายชื่อ) — ปล่อยไว้"""
    rec = {"projects": [{"name": "ก 1.ด.ช. ข ขคง", "members": [], "advisor": ""}]}
    split_glued_members(rec)
    assert rec["projects"][0]["name"] == "ก 1.ด.ช. ข ขคง"
    assert rec["projects"][0]["members"] == []


def test_split_glued_members_ไม่มีโครงงานเลย():
    rec = {"projects": []}
    split_glued_members(rec)
    assert rec["projects"] == []


# --- match_projects_to_rooms -------------------------------------------------
def roster_row(room, teacher):
    return {"room": room, "grade": room.split("/")[0], "plan": "", "course_code": "I21201",
            "subject": "IS 1", "teacher": teacher}


def extracted_rec(room, teacher, names, source="ไฟล์.docx"):
    return {"room": room, "teacher": teacher, "subject": "IS 1", "sources": [source],
            "projects": [{"name": n, "members": [], "advisor": teacher} for n in names]}


def test_match_เติม_projects_และ_source_file_ให้ทุกแถว():
    roster = [roster_row("ม.1/1", "นายสมชาย ใจดี"), roster_row("ม.1/2", "นางสาวมาลี รักเรียน")]
    match_projects_to_rooms(roster, [extracted_rec("ม.1/1", "ครูสมชาย ใจดี", ["ก"], "ม1-1.docx")])
    assert roster[0]["projects"] and roster[0]["source_file"] == "ม1-1.docx"
    assert roster[1]["projects"] == [] and roster[1]["source_file"] == ""


def test_match_ห้องซ้ำสองแผนการเรียนแยกตามนามสกุลครู():
    """ม.1/8 มี 2 แถว (2 ครู) — ไฟล์ของใครต้องเข้าแถวของคนนั้น ไม่ใช่เข้าแถวแรกที่เจอ"""
    roster = [roster_row("ม.1/8", "นายสมชาย ใจดี"), roster_row("ม.1/8", "นางสาวมาลี รักเรียน")]
    extracted = [
        extracted_rec("ม.1/8", "ครูมาลี รักเรียน", ["ของมาลี"], "มาลี.docx"),
        extracted_rec("ม.1/8", "ครูสมชาย ใจดี", ["ของสมชาย"], "สมชาย.docx"),
    ]
    match_projects_to_rooms(roster, extracted)
    assert roster[0]["source_file"] == "สมชาย.docx"
    assert roster[1]["source_file"] == "มาลี.docx"


def test_match_ห้องซ้ำแต่ชื่อครูในไฟล์ไม่ตรงใช้รอบที่สองตามลำดับ():
    roster = [roster_row("ม.2/3", "นายสมชาย ใจดี"), roster_row("ม.2/3", "นางสาวมาลี รักเรียน")]
    match_projects_to_rooms(roster, [
        extracted_rec("ม.2/3", "ไม่ระบุ", ["ก"], "a.docx"),
        extracted_rec("ม.2/3", "ไม่ระบุ", ["ข"], "b.docx"),
    ])
    assert [r["source_file"] for r in roster] == ["a.docx", "b.docx"]


def test_match_record_เดียวไม่ถูกนับซ้ำหลายแถว():
    roster = [roster_row("ม.3/5", "นายสมชาย ใจดี"), roster_row("ม.3/5", "นางสาวมาลี รักเรียน")]
    match_projects_to_rooms(roster, [extracted_rec("ม.3/5", "ไม่ระบุ", ["ก", "ข"])])
    assert sum(1 for r in roster if r["projects"]) == 1


def test_match_โครงงานที่จับคู่ห้องไม่ได้แค่เตือนไม่_throw(caplog):
    """เดิมจุดนี้เขียน sys.stderr ทั้งที่โมดูลไม่ได้ import sys — จับคู่ไม่ได้แม้รายการเดียว
    จะเป็น NameError แล้วล้มทั้งรอบ ทั้งที่เป็นแค่เรื่องที่ต้องเตือน"""
    roster = [roster_row("ม.1/1", "นายสมชาย ใจดี")]
    with caplog.at_level(logging.WARNING, logger="sync.parse_is"):
        match_projects_to_rooms(roster, [extracted_rec("ม.6/9", "ครูไม่มีในบัญชี", ["ก"])])
    assert roster[0]["projects"] == []
    assert "ม.6/9" in caplog.text


def test_match_roster_ว่างไม่_throw():
    match_projects_to_rooms([], [extracted_rec("ม.1/1", "ครูสมชาย ใจดี", ["ก"])])


def test_match_ครูไม่มีนามสกุลไม่จับคู่ด้วยสตริงว่าง():
    """_lastname("") = "" และ "" in อะไรก็จริง — ถ้าไม่กัน แถวที่ไม่มีชื่อครูจะดูดไฟล์ไปหมด"""
    roster = [roster_row("ม.1/1", ""), roster_row("ม.1/1", "นายสมชาย ใจดี")]
    match_projects_to_rooms(roster, [extracted_rec("ม.1/1", "ครูสมชาย ใจดี", ["ก"], "s.docx")])
    assert roster[1]["source_file"] == "s.docx"
    assert roster[0]["projects"] == []


# --- extract_projects: ไฟล์เดียวพัง/หาย ต้องไม่ล้มทั้งรอบ -----------------------
def write_form_docx(path, room_text, teacher, subject, projects):
    """สร้างไฟล์แบบฟอร์มที่ครูส่ง: ตารางหัว (ระดับชั้น/ครูผู้สอน/รายวิชา) + ตารางโครงงาน 4 คอลัมน์"""
    d = docx.Document()
    head = d.add_table(rows=3, cols=2)
    head.cell(0, 0).text, head.cell(0, 1).text = "ระดับชั้น", room_text
    head.cell(1, 0).text, head.cell(1, 1).text = "ครูผู้สอน", teacher
    head.cell(2, 0).text, head.cell(2, 1).text = "รายวิชา", subject
    d.add_paragraph("")
    tbl = d.add_table(rows=1 + len(projects), cols=4)
    for i, h in enumerate(["ลำดับ", "ชื่อโครงงาน", "สมาชิก", "ครูที่ปรึกษา"]):
        tbl.cell(0, i).text = h
    for i, (name, mem) in enumerate(projects, start=1):
        tbl.cell(i, 0).text = str(i)
        tbl.cell(i, 1).text = name
        tbl.cell(i, 2).text = "\n".join(f"{j}. {m}" for j, m in enumerate(mem, start=1))
        tbl.cell(i, 3).text = teacher
    d.save(str(path))
    return path


def test_extract_projects_โฟลเดอร์ว่างได้ลิสต์ว่างไม่_throw(tmp_path, caplog):
    """ไฟล์รูปแบบอิสระที่ hardcode ชื่อไว้ 2 ไฟล์ หายได้ตลอด (ครูเปลี่ยนชื่อ/ลบใน Drive)
    เดิมเรียก docx.Document() ตรง ๆ แล้ว workflow ล้มทุกรอบจนกว่าจะมีคนแก้โค้ด"""
    with caplog.at_level(logging.WARNING, logger="sync.parse_is"):
        assert extract_projects(tmp_path) == []
    assert FREEFORM_KANCHAPHORN in caplog.text
    assert FREEFORM_M1_11 in caplog.text
    assert "ม.1/11" in caplog.text          # warning ต้องบอกว่าข้อมูลห้องไหนจะหายไป
    assert "ม.2/8" in caplog.text


def test_extract_projects_อ่านไฟล์แบบฟอร์มได้(tmp_path):
    write_form_docx(tmp_path / "IS ม.4 ห้อง 3.docx", "ชั้นมัธยมศึกษาปีที่ 4 ห้อง 3",
                    "นายสมชาย ใจดี", "IS 1",
                    [("เครื่องกรองน้ำจากวัสดุเหลือใช้", ["เด็กชาย ก กขค", "เด็กหญิง ข ขคง"]),
                     ("ปุ๋ยหมักจากเศษอาหาร", ["เด็กชาย ค คงจ"])])
    recs = extract_projects(tmp_path)
    assert len(recs) == 1
    rec = recs[0]
    assert rec["room"] == "ม.4/3"
    assert rec["teacher"] == "นายสมชาย ใจดี"
    assert rec["subject"] == "IS 1"
    assert [p["name"] for p in rec["projects"]] == ["เครื่องกรองน้ำจากวัสดุเหลือใช้", "ปุ๋ยหมักจากเศษอาหาร"]
    assert rec["projects"][0]["members"] == ["เด็กชาย ก กขค", "เด็กหญิง ข ขคง"]
    assert rec["sources"] == ["IS ม.4 ห้อง 3.docx"]


def test_extract_projects_ไฟล์_docx_เสียข้ามไฟล์เดียว(tmp_path, caplog):
    (tmp_path / "ไฟล์เสีย.docx").write_bytes(b"not a zip at all")
    write_form_docx(tmp_path / "IS ม.4 ห้อง 3.docx", "ม.4/3", "นายสมชาย ใจดี", "IS 1",
                    [("โครงงานที่ยังอ่านได้", ["เด็กชาย ก กขค"])])
    with caplog.at_level(logging.WARNING, logger="sync.parse_is"):
        recs = extract_projects(tmp_path)
    assert [r["room"] for r in recs] == ["ม.4/3"]
    assert "ไฟล์เสีย.docx" in caplog.text


def test_extract_projects_ไฟล์_pdf_เสียข้ามไฟล์เดียว(tmp_path, caplog):
    (tmp_path / "ไฟล์เสีย.pdf").write_bytes(b"%PDF-1.4 not really a pdf")
    write_form_docx(tmp_path / "IS ม.5 ห้อง 1.docx", "ม.5/1", "นางสาวมาลี รักเรียน", "IS 1",
                    [("โครงงานที่ยังอ่านได้", ["เด็กหญิง ข ขคง"])])
    with caplog.at_level(logging.WARNING, logger="sync.parse_is"):
        recs = extract_projects(tmp_path)
    assert [r["room"] for r in recs] == ["ม.5/1"]
    assert "ไฟล์เสีย.pdf" in caplog.text


def test_extract_projects_ข้ามเอกสารที่ไม่ใช่รายงานของครู(tmp_path):
    write_form_docx(tmp_path / "IS_สรุปเนื้อหา.docx", "ม.4/3", "นายสมชาย ใจดี", "IS 1",
                    [("ไม่ควรถูกนับ", [])])
    assert extract_projects(tmp_path) == []


def test_extract_projects_ไฟล์รูปแบบอิสระ_ม1_11(tmp_path, caplog):
    """ครูชยพลส่งเป็นข้อความเรียง ไม่ได้ใช้แบบฟอร์ม — ย่อหน้าที่ขึ้นต้นด้วยคำนำหน้าชื่อ
    คือสมาชิกของโครงงานก่อนหน้า"""
    d = docx.Document()
    for t in ["ชื่อหัวข้อโครงงาน", "กีฬาพื้นบ้านกับสุขภาพ", "เด็กชาย ก กขค", "เด็กหญิง ข ขคง",
              "ทักษะการเล่นตะกร้อ", "เด็กชาย ค คงจ"]:
        d.add_paragraph(t)
    d.save(str(tmp_path / FREEFORM_M1_11))
    with caplog.at_level(logging.WARNING, logger="sync.parse_is"):
        recs = extract_projects(tmp_path)
    assert [r["room"] for r in recs] == ["ม.1/11"]
    projs = recs[0]["projects"]
    assert [p["name"] for p in projs] == ["กีฬาพื้นบ้านกับสุขภาพ", "ทักษะการเล่นตะกร้อ"]
    assert projs[0]["members"] == ["เด็กชาย ก กขค", "เด็กหญิง ข ขคง"]
    assert projs[1]["members"] == ["เด็กชาย ค คงจ"]
    assert FREEFORM_KANCHAPHORN in caplog.text   # อีกไฟล์ยังหาย ต้องเตือนแต่ไม่ล้ม


def test_extract_projects_มีแบบฟอร์มของ_ม1_11_แล้วไม่อ่านไฟล์อิสระซ้ำ(tmp_path):
    """เจอจริง 2026-09-09: ครูส่งแบบฟอร์มตามมาทีหลัง ถ้าไม่กันจะนับซ้ำ (13 + 14 = 27 โครงงาน)"""
    write_form_docx(tmp_path / "ม.1 ห้อง 11 (ฟอร์ม).docx", "ม.1/11", "นายชยพล วังสุนทร",
                    "ความรู้เบื้องต้นทางการกีฬา", [("จากแบบฟอร์ม", ["เด็กชาย ก กขค"])])
    d = docx.Document()
    d.add_paragraph("จากไฟล์เดิมไม่ควรถูกนับ")
    d.save(str(tmp_path / FREEFORM_M1_11))
    recs = extract_projects(tmp_path)
    assert len(recs) == 1
    assert [p["name"] for p in recs[0]["projects"]] == ["จากแบบฟอร์ม"]


def test_extract_projects_เรียงตามระดับชั้นแล้วห้อง(tmp_path):
    for room in ["ม.4/10", "ม.1/2", "ม.4/2"]:
        write_form_docx(tmp_path / f"IS {room.replace('/', ' ห้อง ')}.docx", room,
                        "นายสมชาย ใจดี", "IS 1", [(f"โครงงานของ {room}", [])])
    assert [r["room"] for r in extract_projects(tmp_path)] == ["ม.1/2", "ม.4/2", "ม.4/10"]


# --- หนึ่งห้องหนึ่งแหล่ง: .docx ชนะ .pdf ------------------------------------------
#: ข้อความที่สกัดได้จากไฟล์ PDF ที่ครู export จากแบบฟอร์ม — คงอักขระเพี้ยนไว้ตามของจริง
#: ("ห,อง" = "ห้อง", "ผู,สอน" = "ผู้สอน") เพราะ extract_projects มีตารางแก้อักขระพวกนี้อยู่
#: และรูปร่าง "1. ชื่อครู" ต่อท้ายรายชื่อสมาชิกคือต้นเหตุที่ชื่อครูหลุดเข้าไปเป็นนักเรียน
FAKE_PDF_TEXT = """แบบฟอร&มรวบรวมข*อมูลโครงงานนักเรียน
ระดับชั้น / ห,อง {room}
ชื่อครูผู,สอน {teacher}
รายวิชา {subject}
รายละเอียดโครงงานของนักเรียน
ลำดับ ชื่อโครงงาน รายชื่อสมาชิกในกลุMม ครูที่ปรึกษาโครงงาน หมายเหตุ
1 โครงงานแรกจากไฟล์ PDF
1. เด็กชาย ก กขค
2. เด็กหญิง ข ขคง
1. {teacher}

2 โครงงานที่สองจากไฟล์ PDF
1. เด็กชาย ค คงจ
1. {teacher}

รวมจำนวนนักเรียน  3 คน
หมายเหตุ: กรุณาระบุชื่อโครงงานและรายชื่อสมาชิกให,ครบถ,วน หากมีมากกวMา 6 กลุMม สามารถเพิ่มแถวในตารางได,ตาม
ความเหมาะสม
"""


def fake_pdf(monkeypatch, texts):
    """สร้างไฟล์ .pdf หลอก ๆ แล้วให้ _read_pdf_text คืนข้อความที่กำหนดไว้ต่อชื่อไฟล์

    เขียน PDF ที่มีข้อความไทยจริงในเทสไม่ได้ (pypdf อ่าน ไม่เขียน) — สิ่งที่ต้องคุมคือ
    "สกัดข้อความได้แล้วทำอะไรต่อ" จึงหลอกที่ชั้นอ่านไฟล์ ไม่ใช่ที่ไฟล์
    """
    import sync.parse_is as m
    monkeypatch.setattr(m, "_read_pdf_text", lambda p, *a, **k: texts.get(p.name))


def test_extract_projects_ห้องมีทั้ง_docx_และ_pdf_นับแค่แบบฟอร์ม(tmp_path, monkeypatch):
    """เจอจริง 2026-10-19: ครูอัป Drive ทั้งสองนามสกุลของเนื้อหาเดียวกัน ม.1/1 จึงโชว์
    27 โครงงาน (9 x 3 ไฟล์) ยึด .docx เพราะข้อความที่สกัดจาก PDF เพี้ยน"""
    write_form_docx(tmp_path / "ข้อมูลโครงงาน ม101.docx", "ม.1/1", "นางสาวมาลี รักเรียน", "IS 1",
                    [("โครงงานจากแบบฟอร์ม", ["เด็กชาย ก กขค"])])
    (tmp_path / "ข้อมูลโครงงาน ม101.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "ข้อมูลโครงงาน ม101ok.pdf").write_bytes(b"%PDF-1.4")
    fake_pdf(monkeypatch, {
        n: FAKE_PDF_TEXT.format(room="ม.1/1", teacher="นางสาวมาลี รักเรียน", subject="IS 1")
        for n in ("ข้อมูลโครงงาน ม101.pdf", "ข้อมูลโครงงาน ม101ok.pdf")
    })
    recs = extract_projects(tmp_path)
    assert len(recs) == 1
    assert [p["name"] for p in recs[0]["projects"]] == ["โครงงานจากแบบฟอร์ม"]
    assert recs[0]["sources"] == ["ข้อมูลโครงงาน ม101.docx"]


def test_extract_projects_pdf_หลายไฟล์ของห้องเดียวกันนับครั้งเดียว(tmp_path, monkeypatch):
    """ไม่มีแบบฟอร์มเลย: ใช้ PDF ได้ แต่ไฟล์แรกเท่านั้น ("ok" มาก่อนตามลำดับชื่อไฟล์)"""
    for n in ("รายงาน ม209.pdf", "รายงาน ม209ok.pdf"):
        (tmp_path / n).write_bytes(b"%PDF-1.4")
    fake_pdf(monkeypatch, {
        n: FAKE_PDF_TEXT.format(room="ม.2/9", teacher="นางสาวมาลี รักเรียน", subject="IS 1")
        for n in ("รายงาน ม209.pdf", "รายงาน ม209ok.pdf")
    })
    recs = extract_projects(tmp_path)
    assert len(recs) == 1
    assert [p["name"] for p in recs[0]["projects"]] == ["โครงงานแรกจากไฟล์ PDF", "โครงงานที่สองจากไฟล์ PDF"]
    assert recs[0]["sources"] == ["รายงาน ม209.pdf"]


def test_extract_projects_pdf_ของห้องที่ไม่มีแบบฟอร์มยังถูกใช้(tmp_path, monkeypatch):
    """กฎ "docx ชนะ pdf" ต้องเป็นรายห้อง ไม่ใช่ทั้งโฟลเดอร์ — ห้องที่ส่งมาแค่ PDF ต้องไม่หาย"""
    write_form_docx(tmp_path / "IS ม.4 ห้อง 3.docx", "ม.4/3", "นายสมชาย ใจดี", "IS 1",
                    [("โครงงานของ ม.4/3", [])])
    (tmp_path / "รายงาน ม209.pdf").write_bytes(b"%PDF-1.4")
    fake_pdf(monkeypatch, {"รายงาน ม209.pdf": FAKE_PDF_TEXT.format(
        room="ม.2/9", teacher="นางสาวมาลี รักเรียน", subject="IS 1")})
    assert [r["room"] for r in extract_projects(tmp_path)] == ["ม.2/9", "ม.4/3"]


def test_extract_projects_pdf_ไม่นับชื่อครูและข้อความท้ายตารางเป็นนักเรียน(tmp_path, monkeypatch):
    """ยอด "นักเรียน" ในรายงานเคยสูงกว่าจริง (1,476 คน) เพราะชื่อครูที่ปรึกษาและข้อความ
    ท้ายตารางในไฟล์ PDF หลุดเข้าไปอยู่ในช่องรายชื่อสมาชิก"""
    (tmp_path / "รายงาน ม209.pdf").write_bytes(b"%PDF-1.4")
    fake_pdf(monkeypatch, {"รายงาน ม209.pdf": FAKE_PDF_TEXT.format(
        room="ม.2/9", teacher="นางสาวมาลี รักเรียน", subject="IS 1")})
    projs = extract_projects(tmp_path)[0]["projects"]
    assert projs[0]["members"] == ["เด็กชาย ก กขค", "เด็กหญิง ข ขคง"]
    assert projs[1]["members"] == ["เด็กชาย ค คงจ"]       # บรรทัดสุดท้ายของตาราง: ท้ายตารางต่อท้ายมา
    assert projs[0]["advisor"] == "นางสาวมาลี รักเรียน"   # ยังต้องรู้ว่าใครเป็นครูที่ปรึกษา


# --- members: ช่องรายชื่อสมาชิกต้องมีแต่ชื่อนักเรียน --------------------------------
def test_members_ไม่นับชื่อครูที่ปรึกษาเป็นสมาชิก():
    assert members("1. เด็กชาย ก กขค\n2. นางสาวมาลี รักเรียน", "นางสาวมาลี รักเรียน") == ["เด็กชาย ก กขค"]


def test_members_ชื่อครูเว้นวรรคหรือใส่จุดไม่เหมือนกันก็ยังคัดออก():
    """ข้อความจาก PDF เว้นวรรค/ใส่จุดไม่เหมือนต้นฉบับ เทียบสตริงตรง ๆ จึงไม่พอ"""
    assert members("1. เด็กชาย ก กขค\n2. นางสาว มาลี  รักเรียน", "นางสาวมาลี รักเรียน") == ["เด็กชาย ก กขค"]
    assert members("1. เด็กชาย ก กขค\n2. ครูมาลี รักเรียน", "นางสาวมาลี รักเรียน") == ["เด็กชาย ก กขค"]


def test_members_คนละคนที่ชื่อขึ้นต้นเหมือนครูต้องไม่ถูกคัดออก():
    assert members("1. เด็กหญิงมาลี ขยันเรียน", "นางสาวมาลี รักเรียน") == ["เด็กหญิงมาลี ขยันเรียน"]


@pytest.mark.parametrize("junk", [
    "รวมจำนวนนักเรียน 21 คน",
    "หมายเหตุ: กรุณาระบุชื่อโครงงานและรายชื่อสมาชิกให้ครบถ้วน",
    "ลำดับ ชื่อโครงงาน รายชื่อสมาชิกในกลุ่ม ครูที่ปรึกษาโครงงาน",
    "รายชื่อสมาชิกในกลุ่ม",
    "ครูที่ปรึกษาร่วม",
])
def test_members_ข้อความหัวท้ายตารางไม่ถูกนับเป็นชื่อคน(junk):
    assert members(f"1. เด็กชาย ก กขค\n{junk}") == ["เด็กชาย ก กขค"]


def test_members_หยุดที่ข้อความท้ายตารางไม่เก็บเศษประโยคบรรทัดถัดไป():
    """ข้อความท้ายตารางยาวหลายบรรทัด บรรทัดต่อ ๆ ไปเป็นเศษประโยคที่ดูเหมือนชื่อคนได้"""
    s = ("1. เด็กชาย ก กขค\nหมายเหตุ: กรุณาระบุชื่อโครงงานให้ครบถ้วน หากมีมากกว่า 6 กลุ่ม\n"
         "ความเหมาะสม")
    assert members(s) == ["เด็กชาย ก กขค"]


def test_members_ช่องว่างหรือขีดได้ลิสต์ว่าง():
    assert members("") == []
    assert members("-") == []


def test_parse_tbl_ชื่อครูในช่องสมาชิกถูกคัดออกตามคอลัมน์ครูที่ปรึกษา(tmp_path):
    """ไฟล์แบบฟอร์มบางไฟล์พิมพ์ชื่อครูต่อท้ายรายชื่อสมาชิกด้วย"""
    write_form_docx(tmp_path / "IS ม.4 ห้อง 3.docx", "ม.4/3", "นายสมชาย ใจดี", "IS 1",
                    [("โครงงานทดสอบ", ["เด็กชาย ก กขค", "นายสมชาย ใจดี"])])
    projs = extract_projects(tmp_path)[0]["projects"]
    assert projs[0]["members"] == ["เด็กชาย ก กขค"]
    assert projs[0]["advisor"] == "นายสมชาย ใจดี"


def test_extract_projects_ตารางเดิมซ้ำสองรอบในไฟล์เดียวนับครั้งเดียว(tmp_path):
    """ครูก็อปตารางทิ้งไว้ท้ายเอกสาร — ชื่อโครงงาน + สมาชิกตรงกันเป๊ะคือสำเนา"""
    d = docx.Document()
    head = d.add_table(rows=3, cols=2)
    head.cell(0, 0).text, head.cell(0, 1).text = "ระดับชั้น", "ม.1/1"
    head.cell(1, 0).text, head.cell(1, 1).text = "ครูผู้สอน", "นางสาวมาลี รักเรียน"
    head.cell(2, 0).text, head.cell(2, 1).text = "รายวิชา", "IS 1"
    for _ in range(2):                      # ตารางโครงงานเดิมสองรอบ
        d.add_paragraph("")
        tbl = d.add_table(rows=2, cols=4)
        for i, h in enumerate(["ลำดับ", "ชื่อโครงงาน", "สมาชิก", "ครูที่ปรึกษา"]):
            tbl.cell(0, i).text = h
        tbl.cell(1, 0).text, tbl.cell(1, 1).text = "1", "บันไดงูกินฝุ่น"
        tbl.cell(1, 2).text, tbl.cell(1, 3).text = "1. เด็กชาย ก กขค", "นางสาวมาลี รักเรียน"
    d.save(str(tmp_path / "ข้อมูลโครงงาน ม101.docx"))
    recs = extract_projects(tmp_path)
    assert [p["name"] for p in recs[0]["projects"]] == ["บันไดงูกินฝุ่น"]


def test_extract_projects_สองกลุ่มชื่อโครงงานเดียวกันแต่สมาชิกคนละชุดต้องอยู่ครบ():
    """ม.1/4 มีจริง: "นิทานพื้นบ้าน เรื่องเมืองลับแล" สองกลุ่ม คนละสมาชิก ห้ามยุบเป็นกลุ่มเดียว"""
    import sync.parse_is as m
    rows_a = [["ลำดับ", "ชื่อโครงงาน", "สมาชิก", "ครูที่ปรึกษา"],
              ["1", "นิทานพื้นบ้าน เรื่องเมืองลับแล", "1. เด็กชาย ก กขค", "นายสมชาย ใจดี"],
              ["2", "นิทานพื้นบ้าน เรื่องเมืองลับแล", "1. เด็กหญิง ข ขคง", "นายสมชาย ใจดี"]]
    assert len(m.parse_tbl(rows_a)) == 2
