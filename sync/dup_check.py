"""ตรวจหานักเรียนที่มีชื่ออยู่เกิน 1 โครงงาน -> คำเตือนที่หน้าเว็บเอาไปแสดง

ทำไมเป็น "คำเตือน" ไม่ใช่ "ตัดออกอัตโนมัติ" (ผู้ใช้สั่งเมื่อ 2026-10-19): โปรแกรมไม่รู้ว่า
เด็กอยู่กลุ่มไหนจริง ถ้าตัดเองอาจตัดกลุ่มที่ถูกออก — ให้ครูเจ้าของห้องเห็นแล้วไปแก้ไฟล์ต้นทางเอง
ต่างจาก "ไฟล์ซ้ำ" (docx + pdf ของเนื้อหาเดียวกัน) ที่ตัดอัตโนมัติได้เพราะเป็นสำเนาตรง ๆ
ดู extract_projects() ใน parse_is.py

สามเรื่องที่ทำให้เตือนผิดเป็นร้อยรายการถ้าไม่ระวัง (เจอจริงตอนไล่ report.json ที่ deploy อยู่):
  1. ต้องตรวจ "หลัง" ตัดไฟล์ซ้ำแล้ว ไม่งั้นแถวสำเนาทำให้เด็กทุกคนในห้องนั้นถูกเตือนหมด
  2. ต้องกรองชื่อครูออก — ครูคนเดียวคุมหลายโครงงานในห้องเดียวกัน และ ม.4-ม.5 นักเรียนใช้
     คำนำหน้า นาย/นางสาว เหมือนครู แยกด้วยคำนำหน้าไม่ได้ จึงเทียบกับ advisor ของแถวนั้น
     และกับรายชื่อครูทั้งระบบ
  3. ชื่อที่ครูกรอกมาแค่ชื่อต้น (ไม่มีนามสกุล) มีอยู่ ~200 จาก ~1,500 ชื่อ เด็กสองคนชื่อต้น
     เดียวกันเป็นเรื่องปกติ — ชื่อ+สกุลครบที่ซ้ำ = "confirmed", ชื่อเดี่ยว = "likely"
     (เตือนในห้องเดียวกันเท่านั้น ข้ามห้องไม่เตือนชื่อเดี่ยวเลย)
"""
from __future__ import annotations

import re
from collections import defaultdict


#: คำนำหน้าชื่อที่เจอในไฟล์จริง — เรียงยาวก่อนสั้นตอนประกอบ regex ("นางสาว" ต้องชนะ "นาง")
#: มีทั้งแบบมีจุดท้ายและไม่มี เพราะครูพิมพ์ทั้ง "น.ส." และ "น.ส ดาว" (ตัวหลังเจอใน ม.4/1)
TITLES = ("เด็กชาย", "เด็กหญิง", "ด.ช.", "ด.ญ.", "ด.ช", "ด.ญ", "นางสาว", "น.ส.", "น.ส",
          "นาย", "นาง", "คุณครู", "ครู", "ว่าที่ ร.ต. หญิง", "ว่าที่ ร.ต.")
_TITLE_RE = re.compile(r"^(?:%s)\s*" % "|".join(
    re.escape(t) for t in sorted(TITLES, key=len, reverse=True)))

#: สระ "ำ" ที่หลุดเป็น "ค า" ตอนสกัดข้อความจาก PDF — ต้องซ่อมก่อนลบช่องว่าง ไม่งั้น
#: "ค าสอน" จะกลายเป็น "คาสอน" แล้วไม่แมตช์กับ "คำสอน" ที่มาจากไฟล์ .docx
_SARA_AM_RE = re.compile(r"([ก-ฮ])\s+า")


def _strip_title(s: str) -> str:
    return _TITLE_RE.sub("", _SARA_AM_RE.sub(r"\1ำ", s or ""), count=1)


def name_key(s: str) -> str:
    """ชื่อคน -> คีย์สำหรับเทียบว่าเป็นคนเดียวกัน (ตัดคำนำหน้า ช่องว่าง จุด ขีด)"""
    if not s:
        return ""
    return re.sub(r"[ .\-_–]", "", _strip_title(s))


def has_surname(s: str) -> bool:
    """มีนามสกุลด้วยไหม — ชื่อเดี่ยวที่ซ้ำกันเชื่อถือไม่ได้เท่าชื่อ+สกุลครบ

    คำที่เป็นเครื่องหมายล้วน ("-", "–") ไม่นับเป็นนามสกุล: ครูใส่ขีดไว้แทนช่องว่าง เจอจริงที่
    ม.1/3 "เด็กชายอาทิตย์ –" ซึ่งถ้านับเป็นชื่อเต็มจะไปเตือนข้ามห้องกับเด็กชื่ออาทิตย์ห้องอื่น
    """
    if not s:
        return False
    words = [w for w in _strip_title(s).split() if re.search(r"[^\W_]", w)]
    return len(words) >= 2


def find_room_duplicates(projects, teacher_names=()) -> list[dict]:
    """หาชื่อที่ปรากฏเกินครั้งเดียว "ในห้องเดียวกัน" -> รายการคำเตือน

    `projects` = [{room, ord, name, members: list[str], advisor}] (หนึ่งรายการต่อโครงงาน)
    นับทั้งกรณีซ้ำข้ามโครงงาน และซ้ำสองครั้งในโครงงานเดียว (ครูพิมพ์ชื่อเดิมสองรอบ —
    เจอจริงที่ ม.3/5 โครงงาน #2) ไม่เทียบข้ามห้องเด็ดขาด คนละห้องคือคนละคน
    """
    by_room: dict[str, list[dict]] = defaultdict(list)
    for p in projects:
        by_room[p["room"]].append(p)

    global_teachers = {name_key(t) for t in teacher_names if name_key(t)}
    out: list[dict] = []

    for room, items in by_room.items():
        # ครูที่ปรึกษาของทุกโครงงานในห้องนี้ + ครูทั้งระบบ = ชื่อที่ไม่ใช่นักเรียน
        teachers = global_teachers | {name_key(p.get("advisor") or "") for p in items}
        teachers.discard("")

        seen: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
        for p in items:
            for member in p.get("members") or []:
                key = name_key(member)
                if not key or key in teachers:
                    continue
                seen[key].append((member, p["ord"], p["name"]))

        for occurrences in seen.values():
            if len(occurrences) < 2:
                continue
            first = occurrences[0][0]
            ord_to_project: dict[int, str] = {}
            for _, o, project_name in occurrences:
                ord_to_project.setdefault(o, project_name)
            ords = sorted(ord_to_project)
            out.append({
                "room": room,
                "student": first,
                "level": "confirmed" if has_surname(first) else "likely",
                "count": len(occurrences),
                "ords": ords,
                "projects": [ord_to_project[o] for o in ords],
            })

    return sorted(out, key=lambda w: (w["room"], w["ords"][0], w["student"]))


def find_cross_room_duplicates(projects, teacher_names=()) -> list[dict]:
    """ชื่อ+นามสกุลครบ ที่โผล่ในหลายห้อง -> คำเตือนอีกชุด (เด็กย้ายห้อง/กรอกผิดห้อง)

    ชื่อเดี่ยวไม่เตือนข้ามห้องเลย เพราะเด็กชื่อต้นเดียวกันคนละห้องเป็นเรื่องธรรมดา
    """
    global_teachers = {name_key(t) for t in teacher_names if name_key(t)}
    advisors = {name_key(p.get("advisor") or "") for p in projects}
    teachers = (global_teachers | advisors) - {""}

    seen: dict[str, dict[str, str]] = defaultdict(dict)   # key -> {room: ชื่อที่พิมพ์มา}
    for p in projects:
        for member in p.get("members") or []:
            key = name_key(member)
            if not key or key in teachers or not has_surname(member):
                continue
            seen[key].setdefault(p["room"], member)

    out = []
    for rooms in seen.values():
        if len(rooms) < 2:
            continue
        out.append({"student": next(iter(rooms.values())), "rooms": sorted(rooms)})
    return sorted(out, key=lambda w: (w["rooms"][0], w["student"]))


__all__ = ["find_cross_room_duplicates", "find_room_duplicates", "has_surname", "name_key"]
