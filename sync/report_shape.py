"""แปลง roster ที่ parse มาแล้ว -> dict พร้อมเขียนเป็น report.json

รูปร่างผลลัพธ์ตรงกับที่ `GET /api/report` ของ repo เดิมส่งตอน role = viewer
(`include_members=False`) frontend จึงใช้ของเดิมต่อได้โดยแก้แค่ที่มาของข้อมูล

รายงานนี้รวม "ชื่อสมาชิกโครงงาน" ไว้ด้วย และไฟล์ถูก commit ขึ้น repo public — ผู้ใช้ตัดสินใจ
เองเมื่อ 2026-10-18 หลังได้รับแจ้งความเสี่ยงแล้ว (เสิร์ชเอนจินเก็บ index ได้, Wayback เก็บถาวร
ได้, ลบทีหลังเรียกคืนไม่ได้, นักเรียนเป็นผู้เยาว์) เหตุผลคือโครงงานเหล่านี้จัดแสดงเปิดเผยอยู่แล้ว
ถ้าจะกลับไปซ่อนชื่อ: ตัดคีย์ members ออกจาก dict ของ project แล้วตั้ง includes_members เป็น False
"""
from __future__ import annotations



def _digits(s: str, default: int = 99) -> int:
    """ดึงเฉพาะตัวเลขจากข้อความแล้วแปลงเป็น int — "ม.2" -> 2, "" -> default"""
    d = "".join(ch for ch in s if ch.isdigit())
    return int(d) if d else default


def _room_key(room: str) -> tuple[int, int]:
    """"ม.2/10" -> (2, 10) เพื่อให้ ม.2/10 มาหลัง ม.2/9 ไม่ใช่หลัง ม.2/1 แบบเรียงตัวอักษร"""
    grade, _, number = room.partition("/")
    return (_digits(grade), _digits(number))


def roster_to_report(roster: list[dict], *, last_synced_at: str | None = None) -> dict:
    """รวม roster หลายแถวให้เหลือห้องละ 1 รายการ แล้วสรุปเป็นโครงสร้างสำหรับหน้าเว็บ

    ห้องหนึ่งมีได้หลายแถวใน roster (1 แถวต่อ "รายการจัดครูเข้าสอน" เช่น ม.1/8 แยกดนตรีไทย/
    ดนตรีสากล เป็น 2 แถว คนละครู) จึงต้องยุบด้วยชื่อห้องแล้วรวม plans/teachers/projects เข้าด้วยกัน
    """
    rooms: dict[str, dict] = {}
    for row in roster:
        entry = rooms.setdefault(
            row["room"],
            {
                "room": row["room"],
                "grade": row["grade"],
                "plans": [],
                "teachers": [],
                "submitted": False,
                "projects": [],
            },
        )
        entry["submitted"] = entry["submitted"] or bool(row.get("projects"))

        plan = {
            "plan": row.get("plan") or "",
            "course_code": row.get("course_code") or "",
            "subject": row.get("subject") or "",
        }
        if plan not in entry["plans"]:  # (plan, course_code, subject) ซ้ำไม่ต้องเก็บสองรอบ
            entry["plans"].append(plan)

        teacher = row.get("teacher") or ""
        if teacher and teacher not in entry["teachers"]:
            entry["teachers"].append(teacher)

        for project in row.get("projects") or []:
            # สร้าง dict ใหม่ ไม่ copy ของเดิมมาทั้งก้อน — ป้องกัน members หลุดไปกับผลลัพธ์
            members = project.get("members") or []
            entry["projects"].append(
                {
                    "ord": len(entry["projects"]) + 1,  # ไล่ใหม่ 1..n ข้ามทุกแถวของห้องนี้
                    "name": project.get("name") or "",
                    # หน้าเว็บแสดงสตริงนี้ตรง ๆ จึงรวมเป็นบรรทัดเดียวตั้งแต่ตรงนี้
                    "members": ", ".join(members),
                    "member_count": len(members),
                    "advisor": project.get("advisor") or "",
                }
            )

    room_list = sorted(rooms.values(), key=lambda e: _room_key(e["room"]))

    grades: dict[str, dict] = {}
    for entry in room_list:
        g = grades.setdefault(
            entry["grade"], {"grade": entry["grade"], "rooms": 0, "submitted": 0, "projects": 0}
        )
        g["rooms"] += 1
        g["submitted"] += 1 if entry["submitted"] else 0
        g["projects"] += len(entry["projects"])

    return {
        "summary": {
            "rooms": len(room_list),
            "submitted": sum(1 for e in room_list if e["submitted"]),
            "projects": sum(len(e["projects"]) for e in room_list),
            "students": sum(p["member_count"] for e in room_list for p in e["projects"]),
            "teachers": len({t for e in room_list for t in e["teachers"]}),
            "last_synced_at": last_synced_at,
        },
        "grades": sorted(grades.values(), key=lambda g: _digits(g["grade"])),
        "rooms": room_list,
        "includes_members": True,
    }


__all__ = ["roster_to_report"]
