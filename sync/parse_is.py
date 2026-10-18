"""
สร้าง/อัปเดตตาราง is_rooms + is_projects จากไฟล์จริงใน data/files/

ทำไมต้องมี (Phase 7, 2026-09-09): คำถามยอดฮิตของครู ("ม.5/4 ครูใคร", "ครูกัญชพรสอนห้องไหน",
"ห้องไหนยังไม่ส่ง", "ม.2/3 ทำโครงงานอะไร") เป็นคำถามข้อมูลตารางล้วน ๆ เดิมตอบด้วย RAG
(ค้น 5 chunk แล้วให้ LLM สรุป) ซึ่งเห็นข้อมูลไม่ครบทั้งชุด เลยรวบรวมรายการตกหล่น/สลับช่อง
— เก็บเป็นตารางแล้ว query ตรง ตอบเป๊ะและไม่ต้องเรียก LLM เลย

อ่านจาก (ทั้งหมด sync มาจาก Google Drive อยู่แล้ว):
  - รายชื่อครู_รายวิชา_IS_เทอม1.xlsx   -> บัญชีจัดครูเข้าสอน (ห้อง/แผน/รหัสวิชา/วิชา/ครู)
  - IS1_รายวิชาบูรณาการ.html           -> สถานะคำอธิบายรายวิชา (ok/variant/mismatch/missing)
  - *.docx / *.pdf ของครูแต่ละห้อง      -> รายชื่อโครงงาน + สมาชิก + ครูที่ปรึกษา

รันซ้ำได้เสมอ (idempotent): ลบข้อมูลเก่าทั้งตารางแล้วสร้างใหม่จากไฟล์ปัจจุบัน

**ถูกเรียกอัตโนมัติท้าย gdrive.sync.sync_once() ทุกรอบ** (ย้ายมาจาก scripts/build_is_tables.py
เมื่อ 2026-09-10 ด้วยเหตุผลนี้) — เดิมเป็นสคริปต์แยกที่ต้องรันเอง ทำให้ครูส่งไฟล์เข้า Drive แล้ว
RAG เห็นข้อมูลใหม่ทุก 15 นาทีจริง แต่ตารางที่ใช้ตอบคำถาม "ห้องไหนยังไม่ส่ง / ครูใคร / ทำโครงงาน
อะไร" ยังค้างข้อมูลเก่าจนกว่าจะมีคนนึกได้ว่าต้องสั่งรันเอง

ยังสั่งรันมือได้เหมือนเดิม (เช่นตอนแก้ตัว parser แล้วอยากลองก่อน): python3 scripts/build_is_tables.py
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import docx
import openpyxl
import pypdf
from docx.table import Table
from docx.text.paragraph import Paragraph


logger = logging.getLogger(__name__)


class RosterNotFoundError(RuntimeError):
    """ยังไม่มีไฟล์บัญชีจัดครูเข้าสอนใน data/files/ — ไม่ใช่ "พัง" แต่คือ "ยังไม่มีข้อมูลให้ build"

    เกิดได้ปกติบนเครื่องที่เพิ่งติดตั้ง/ยังไม่ได้ sync จาก Drive รอบแรก ผู้เรียก (gdrive.sync)
    จึงถือเป็น skip ไม่ใช่ error ของรอบ sync
    """

ROOM_OVERRIDE = {"IS ชั้น ม.4 ห้อง 10 ภาคเรียนที่1-2569 (วิชางานดอกไม้ใบตอง).docx": "ม.4/10"}
JUNK = re.compile(r"^(รวมจำนวนนักเรียน|ชื่อโครงงาน|ลำดับ|หมายเหตุ)")
NAMEPFX = r"(?:เด็กชาย|เด็กหญิง|ด\.ช\.|ด\.ญ\.|นางสาว|น\.ส\.|นาย|นาง|ว่าที่)"
SKIP_DOCS = ("IS_สรุปเนื้อหา", "STEAM4INNOVATOR", "กลยุทธ์", "บทบาทครูยุคใหม่",
             "พลิกบทบาทครู", "รายงานสรุปเชิงปฏิบัติการ", "หลักสูตรโรงเรียน", "IS_คำอธิบาย",
             "IS_โครงงานรายห้อง", "IS_ภาพรวมสถานะงาน")

# ไฟล์รูปแบบอิสระ 2 ไฟล์ที่ต้องอ่านด้วย logic เฉพาะ (ครูไม่ได้ใช้แบบฟอร์ม) — ชื่อไฟล์ตั้งโดย
# ครู เปลี่ยน/ลบได้ตลอดใน Drive จึงต้องผ่าน _read_docx() เสมอ ห้ามเรียก docx.Document() ตรง ๆ
FREEFORM_KANCHAPHORN = "IS 1 ครูกัญชพร M 208-M 2011.docx"
FREEFORM_M1_11 = "ม.1 ห้อง 11.docx"


def _read_docx(path: Path, missing_note: str = ""):
    """เปิด .docx แบบ "ไฟล์เดียวพังไม่ล้มทั้งรอบ" — คืน None ถ้าเปิดไม่ได้

    ทำตามแบบ drive.mirror_folder ที่ถือว่าไฟล์เดียวพังเป็น warning ไม่ใช่ error ของรอบ sync
    เดิมบางจุดเรียก docx.Document() กับชื่อไฟล์ที่ hardcode ไว้ตรง ๆ ถ้าครูเปลี่ยนชื่อหรือลบไฟล์
    นั้นใน Drive workflow จะล้มทุกรอบจนกว่าจะมีคนแก้โค้ด โดยไม่มีอะไรบอกว่าทำไม
    """
    if not path.exists():
        logger.warning("ไม่พบไฟล์ %s — ข้ามไฟล์นี้%s", path.name, missing_note)
        return None
    try:
        return docx.Document(str(path))
    except Exception as exc:  # ไฟล์เสีย/ไม่ใช่ zip/ถูกตัดกลางทางตอน sync
        logger.warning("อ่านไฟล์ %s ไม่ได้ (%s) — ข้ามไฟล์นี้%s", path.name, exc, missing_note)
        return None


def _read_pdf_text(path: Path) -> str | None:
    """อ่านข้อความทุกหน้าของ PDF — คืน None ถ้าไฟล์เสีย/เข้ารหัส (ข้ามไฟล์เดียว ไม่ล้มทั้งรอบ)"""
    try:
        return "\n".join((pg.extract_text() or '') for pg in pypdf.PdfReader(str(path)).pages)
    except Exception as exc:
        logger.warning("อ่านไฟล์ %s ไม่ได้ (%s) — ข้ามไฟล์นี้ ข้อมูลโครงงานของห้องในไฟล์นี้จะหายไปจากรายงาน",
                       path.name, exc)
        return None

def norm_room(s):
    """แปลงข้อความห้องเรียนทุกแบบที่ครูเขียนจริง -> "ม.3/7"

    รูปแบบที่เจอในไฟล์จริง (แต่ละครูเขียนไม่เหมือนกันเลย):
      "ม.3/7" / "ม3/7" / "ม. 3 / 7"
      "มัธยมศึกษาปีที่ 3/7" / "ชั้นมัธยมศึกษาปีที่ 3/7"
      "ม.3 ห้อง 7"
      "ชั้นมัธยมศึกษาปีที่ 3 ห้อง 7"   <- เจอ 2026-09-09 ในไฟล์ ม.3/7 ที่ครูเพิ่งส่ง
      "ม.3ทับ7"                        <- ชื่อไฟล์ใช้คำว่า "ทับ" แทน /
    """
    if not s: return None
    s = re.sub(r'\s+', ' ', s)
    for pat in (
        r'(?:มัธยมศึกษาปีที่\s*|ม\.?\s*)([1-6])\s*/\s*(\d{1,2})',
        r'(?:มัธยมศึกษาปีที่|ม\.?)\s*([1-6])\s*(?:ห้อง|ทับ)\s*(\d{1,2})',
    ):
        m = re.search(pat, s)
        if m: return f"ม.{m.group(1)}/{m.group(2)}"
    return None

def clean(s):
    s = re.sub(r'[.…]{3,}', ' ', (s or ''))
    return re.sub(r'\s+', ' ', s).strip(' .·-')

def members(s):
    if not s: return []
    out = []
    for x in re.split(r'\n+|(?<=\S)\s(?=\d{1,2}\s*[.)]\s*'+NAMEPFX+')', s):
        x = clean(re.sub(r'^\s*\d{1,2}\s*[.)]\s*', '', x))
        if x and x not in ('-', '–') and not x.startswith('รวม'): out.append(x)
    return out

def parse_tbl(rows):
    out = []
    start = 1 if 'ลำดับ' in ' '.join(rows[0]) else 0
    for r in rows[start:]:
        if len(r) < 3: continue
        nm = clean(r[1])
        if not nm or nm in ('-', '–') or JUNK.match(nm) or len(nm) < 4: continue
        out.append({'name': nm, 'members': members(r[2]),
                    'advisor': clean(re.sub(r'^\s*\d\s*[.)]\s*', '', r[3] if len(r) > 3 else ''))})
    return out


def extract_projects(files_dir: Path) -> list[dict]:
    """สกัดโครงงานจากไฟล์ที่ครูส่ง -> [{room, teacher, subject, projects[], sources[]}]
    (logic นี้ทดสอบจริงแล้วกับไฟล์ทั้ง 28 ไฟล์ ได้ 225 โครงงาน / 788 รายชื่อ ครบถ้วน)"""
    D = files_dir
    recs = {}
    def add(room, teacher, subject, projs, src):
        if not room or not projs: return
        e = recs.setdefault((room, teacher or ''),
                            {'room': room, 'teacher': teacher or '', 'subject': subject or '', 'projects': [], 'sources': []})
        if subject and not e['subject']: e['subject'] = subject
        e['projects'] += projs
        if src not in e['sources']: e['sources'].append(src)

    for p in sorted(D.glob('*.docx')):
        if any(k in p.name for k in SKIP_DOCS): continue
        d = _read_docx(p, " ข้อมูลโครงงานของห้องในไฟล์นี้จะหายไปจากรายงาน")
        if d is None: continue
        cur_room = cur_t = cur_s = None; pend = None
        for ch in d.element.body.iterchildren():
            if ch.tag.endswith('}p'):
                t = Paragraph(ch, d).text.strip()
                if 'รายละเอียดโครงงาน' in t:
                    r = norm_room(t)
                    if r: pend = r
            elif ch.tag.endswith('}tbl'):
                rows = [[c.text.strip() for c in row.cells] for row in Table(ch, d).rows]
                if not rows: continue
                if 'ระดับชั้น' in ' '.join(rows[0]):
                    cur_room = ROOM_OVERRIDE.get(p.name) or norm_room(rows[0][1]) or cur_room
                    for rr in rows:
                        if 'ครูผู้สอน' in rr[0]: cur_t = clean(rr[1])
                        elif 'รายวิชา' in rr[0]: cur_s = clean(rr[1])
                    pend = None
                elif len(rows[0]) >= 4:
                    add(ROOM_OVERRIDE.get(p.name) or pend or cur_room, cur_t, cur_s, parse_tbl(rows), p.name); pend = None

    # ---------- PDF ----------
    for p in sorted(D.glob('*.pdf')):
        if 'IS 204' in p.name: continue
        raw = _read_pdf_text(p)
        if raw is None: continue
        for a, b in {'ห,อง':'ห้อง','ผู,':'ผู้','ผู;':'ผู้','กลุKม':'กลุ่ม','กลุMม':'กลุ่ม','ข*อ':'ข้อ','ข/อ':'ข้อ'}.items():
            raw = raw.replace(a, b)
        room = norm_room(raw[:900]) or norm_room(p.stem)
        mt = re.search(r'ชื่อครูผู้สอน\s*([^\n]+)', raw); teacher = clean(re.split(r'\s*รายวิชา', mt.group(1))[0]) if mt else ''
        ms = re.search(r'\nรายวิชา\s*([^\n]+)', raw); subject = clean(ms.group(1)) if ms else ''
        body = raw.split('ครูที่ปรึกษาโครงงาน', 1)[-1]
        body = re.sub(r'หมายเหตุ\s+(\d{1,2})\s+', r'\n\1 ', body)   # รายการแรกมักติดอยู่บรรทัดเดียวกับหัวตาราง
        blocks = re.split(r'\n\s*(\d{1,2})\s+(?=\S)', body)
        projs = []
        for i in range(1, len(blocks) - 1, 2):
            chunk = blocks[i + 1]
            parts = re.split(r'\n\s*1\s*\.\s*(?=' + NAMEPFX + ')', chunk, maxsplit=1)
            nm = clean(parts[0])
            mem = []
            if len(parts) > 1:
                seg = '1.' + parts[1]
                lines = [l for l in seg.split('\n') if l.strip()]
                keep = []
                for l in lines:
                    if re.match(r'\s*1\s*\.\s*(?:นางสาว|นาง|นาย|ว่าที่)\s*' + re.escape(teacher.split()[-1] if teacher else 'ZZZ'), l): break
                    keep.append(l)
                mem = members('\n'.join(keep))
            if nm and len(nm) > 5 and not JUNK.match(nm):
                projs.append({'name': nm, 'members': mem, 'advisor': teacher})
        add(room, teacher, subject, projs, p.name)

    # ---------- free-form ----------
    d = _read_docx(D / FREEFORM_KANCHAPHORN,
                   " ข้อมูลโครงงาน ม.2/8-ม.2/11 (ครูกัญชพร วิเชียร) จะหายไปจากรายงาน")
    if d is not None:
        cur = None; buf = {}
        for x in d.paragraphs:
            t = x.text.strip()
            if not t: continue
            r = norm_room(t)
            if r and 'ชั้นมัธยม' in t and len(t) < 40: cur = r; buf.setdefault(r, []); continue
            if cur and len(t) > 5 and 'หัวข้อ' not in t and 'ครูกัญชพร' not in t: buf[cur].append(clean(t))
        for room, titles in buf.items():
            add(room, 'ครูกัญชพร วิเชียร', 'การศึกษาค้นคว้าด้วยตนเอง',
                [{'name': t, 'members': [], 'advisor': 'ครูกัญชพร วิเชียร'} for t in titles],
                FREEFORM_KANCHAPHORN)

    # ไฟล์รูปแบบอิสระ (ไม่ใช้แบบฟอร์ม) — ใช้เฉพาะเมื่อห้องนั้นยังไม่มีไฟล์แบบฟอร์มเลย
    # เจอจริง 2026-09-09: ครูชยพลส่ง "ม.1 ห้อง 11 (ฟอร์ม).docx" ตามมาทีหลัง ถ้าไม่กันจะนับซ้ำ
    # (27 โครงงาน = 13 จากแบบฟอร์ม + 14 จากไฟล์เดิม) — ยึดแบบฟอร์มเป็นหลักเพราะข้อมูลครบกว่า
    if any(k[0] == 'ม.1/11' for k in recs):
        return sorted(recs.values(),
                      key=lambda e: (int(e["room"][2]), int(e["room"].split("/")[1]), e["teacher"]))
    d = _read_docx(D / FREEFORM_M1_11, " ข้อมูลโครงงาน ม.1/11 จะหายไปจากรายงาน")
    if d is not None:
        projs = []; cur = None
        for x in d.paragraphs:
            t = x.text.strip()
            if not t or 'ชื่อหัวข้อโครงงาน' in t: continue
            if re.match(r'^' + NAMEPFX, t):
                if cur: cur['members'].append(clean(t))
            else:
                cur = {'name': clean(t), 'members': [], 'advisor': 'นายชยพล วังสุนทร'}; projs.append(cur)
        add('ม.1/11', 'นายชยพล วังสุนทร', 'ความรู้เบื้องต้นทางการกีฬา', projs, FREEFORM_M1_11)

    return sorted(recs.values(),
                  key=lambda e: (int(e["room"][2]), int(e["room"].split("/")[1]), e["teacher"]))


# ---------------------------------------------------------------------------
# บัญชีจัดครูเข้าสอน (Excel) — แหล่งความจริงว่าห้องไหนเรียนวิชาอะไร ครูคนไหนสอน
# ---------------------------------------------------------------------------
def read_roster(files_dir: Path) -> list[dict]:
    """อ่านบัญชีจัดครูเข้าสอน -> [{room, grade, plan, course_code, subject, teacher}]

    รูปแบบไฟล์: หัวตาราง 2 บรรทัด แล้วข้อมูลเริ่มแถว 3 — คอลัมน์
    A=ชั้น/ห้อง  B=ห้องเรียน/แผนการเรียน  C=จำนวน  D=รหัสวิชา  E=ชื่อวิชา  F=ครูผู้สอน
    แถวที่คอลัมน์ A ว่างคือ "แผนการเรียนย่อยที่ 2 ของห้องเดิม" (เช่น ม.1/8 ดนตรีไทย/ดนตรีสากล)
    จึงต้องจำห้องล่าสุดไว้
    """
    candidates = sorted(files_dir.glob("*รายชื่อครู*IS*.xlsx"))
    if not candidates:
        # SystemExit เดิม (สมัยเป็นสคริปต์ CLI) ใช้ไม่ได้แล้ว — เป็น BaseException ที่ except
        # Exception ของผู้เรียกจับไม่ได้ จะฆ่า sync ทั้งรอบ (เจอจริงตอนย้ายมาเป็นโมดูล 2026-09-10)
        raise RosterNotFoundError(
            f"ไม่พบไฟล์บัญชีจัดครูเข้าสอนใน {files_dir} "
            "(ต้องมีไฟล์ชื่อประมาณ 'รายชื่อครู_รายวิชา_IS_เทอม1.xlsx')"
        )
    ws = openpyxl.load_workbook(str(candidates[0]), data_only=True).worksheets[0]

    rows: list[dict] = []
    cur_room = None
    for r in ws.iter_rows(min_row=3, values_only=True):
        room_cell = clean(str(r[0])) if r[0] else ""
        if room_cell.startswith("ม."):
            cur_room = re.sub(r"\s+", "", room_cell)
        if not cur_room:
            continue
        code = clean(str(r[3])) if r[3] else ""
        subject = clean(str(r[4])) if r[4] else ""
        teacher = clean(str(r[5])) if r[5] else ""
        if not (code or subject or teacher):
            continue  # แถวว่าง/แถวคั่น
        if (
            not teacher
            and rows
            and rows[-1]["room"] == cur_room
            and rows[-1]["course_code"] == (code or "—")
        ):
            # กลุ่มย่อยของรายวิชาเดิมในห้องเดียวกัน (ไม่มีครูกำกับ รหัสวิชาซ้ำ) — รวมกับแถวก่อน
            # เจอจริง: ม.5/4 แบ่ง "ศิลป์คำนวณ 1-25" / "คอมพิวเตอร์ 26-36" ใต้ I30201 เดียวกัน
            if rows[-1]["plan"] and r[1]:
                rows[-1]["plan"] += f" + {clean(str(r[1]))}"
            continue
        rows.append({
            "room": cur_room,
            "grade": cur_room.split("/")[0],
            "plan": clean(str(r[1])) if r[1] else "",
            "course_code": code or "—",
            "subject": subject,
            # ตัดคำต่อท้ายอย่าง "(ปัจจุบัน)" ที่ผู้กรอกใส่ไว้ ไม่ใช่ส่วนหนึ่งของชื่อครู
            "teacher": clean(re.sub(r"\s*\(.*?\)\s*$", "", teacher)),
        })
    return rows


def read_desc_status(files_dir: Path) -> dict[str, str]:
    """อ่านสถานะคำอธิบายรายวิชาจากไฟล์ IS1_รายวิชาบูรณาการ.html -> {รหัสวิชา: status}"""
    f = files_dir / "IS1_รายวิชาบูรณาการ.html"
    if not f.exists():
        return {}
    html = f.read_text(encoding="utf-8", errors="replace")
    i = html.find("window.IS_DATA")
    if i < 0:
        logger.warning("ไฟล์ %s ไม่มี window.IS_DATA — ถือว่าไม่มีสถานะคำอธิบายรายวิชา", f.name)
        return {}
    start = html.find("{", i)
    if start < 0:
        logger.warning("ไฟล์ %s มี window.IS_DATA แต่หา JSON ต่อท้ายไม่เจอ — ข้าม", f.name)
        return {}
    depth, in_str, esc = 0, False, False
    for j in range(start, len(html)):
        ch = html[j]
        if in_str:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': in_str = False
        elif ch == '"': in_str = True
        elif ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(html[start:j + 1])
                except json.JSONDecodeError as exc:
                    # ไฟล์นี้ถูก generate ขึ้นมา ถ้าพังก็ควรแค่ไม่มีสถานะ ไม่ใช่ล้มทั้งรอบ sync
                    logger.warning("JSON ใน %s เสีย (%s) — ถือว่าไม่มีสถานะคำอธิบายรายวิชา", f.name, exc)
                    return {}
                break
    else:
        logger.warning("JSON ใน %s ปิดวงเล็บไม่ครบ — ถือว่าไม่มีสถานะคำอธิบายรายวิชา", f.name)
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        (c.get("code") or "").strip(): c.get("status", "ok")
        for c in data.get("courses", []) if c.get("code")
    }


def _lastname(teacher: str) -> str:
    t = re.sub(r"^(นางสาว|นาง|นาย|ครู|ว่าที่ ร\.ต\. หญิง|ว่าที่ ร\.ต\.)\s*", "", teacher).strip()
    return t.split()[0] if t else ""


def split_glued_members(rec: dict) -> None:
    """แยกรายชื่อสมาชิกที่ติดมากับชื่อโครงงานออก (เจอในไฟล์ PDF บางไฟล์ที่ layout ทำให้
    ข้อความไหลต่อกัน เช่น "ชื่อโครงงาน 1.ด.ช. สมชาย ... 5.ด.ช. สมศักดิ์" — ชื่อในตัวอย่าง
    เป็นชื่อสมมติ ของเดิมยกตัวอย่างด้วยชื่อนักเรียนจริง ซึ่ง repo นี้ public จึงเปลี่ยนทิ้ง)
    """
    for p in rec["projects"]:
        m = re.search(r"\s*\d\s*\.\s*(?=" + NAMEPFX + ")", p["name"])
        if not m:
            continue
        head, tail = p["name"][: m.start()].strip(), p["name"][m.start():]
        if len(head) < 5:
            continue
        found = [clean(re.sub(r"^\s*\d+\s*\.\s*", "", x))
                 for x in re.split(r"\s*\d+\s*\.\s*(?=" + NAMEPFX + ")", tail) if x.strip()]
        p["name"] = head
        if len(found) > len(p["members"]):
            p["members"] = found


def match_projects_to_rooms(roster: list[dict], extracted: list[dict]) -> None:
    """จับคู่ไฟล์โครงงานที่ครูส่ง เข้ากับแถวในบัญชีจัดครูเข้าสอน แบบ 1:1

    จับคู่ 2 รอบ: (1) ห้องตรง + นามสกุลครูตรง (แม่นสุด กันห้องที่มี 2 แผนการเรียน/2 ครู)
    (2) ห้องตรงและยังไม่มีใครถือ record นั้น — กัน record เดียวถูกนับซ้ำหลายแถว
    """
    for row in roster:
        row["projects"] = []
        row["source_file"] = ""
    used: set[int] = set()
    for i, e in enumerate(extracted):
        for row in roster:
            if row["room"] != e["room"] or row["projects"]:
                continue
            if _lastname(row["teacher"]) and _lastname(row["teacher"]) in e["teacher"]:
                row["projects"], row["source_file"] = e["projects"], e["sources"][0]
                used.add(i)
                break
    for i, e in enumerate(extracted):
        if i in used:
            continue
        for row in roster:
            if row["room"] == e["room"] and not row["projects"]:
                row["projects"], row["source_file"] = e["projects"], e["sources"][0]
                used.add(i)
                break
    leftover = [e["room"] for i, e in enumerate(extracted) if i not in used]
    if leftover:
        # เดิมเขียน sys.stderr แต่โมดูลนี้ไม่ได้ import sys — จับคู่ไม่ได้แม้รายการเดียว
        # จะกลายเป็น NameError แล้วล้มทั้งรอบ ทั้งที่เป็นแค่เรื่องที่ต้องเตือน
        logger.warning("จับคู่โครงงานกับบัญชีจัดครูเข้าสอนไม่ได้ %d รายการ: %s", len(leftover), leftover)


NOTES = {
    "ม.4/5": "ไฟล์ระบุครูผู้สอนเป็น น.ส.วัลลภา ทวีอภิรดีปิติ ไม่ตรงกับบัญชีจัดครูเข้าสอน",
    "ม.4/10": "ไฟล์ระบุห้องเป็น ม.4/8 (น่าจะพิมพ์ผิด — ยึดตามชื่อไฟล์และครูผู้สอน)",
    "ม.1/11": "ส่งเป็นข้อความเรียง ไม่ได้ใช้แบบฟอร์ม",
}


def build_roster(files_dir: Path) -> list[dict]:
    """อ่านไฟล์ที่ sync มาจาก Drive แล้วคืน roster ในหน่วยความจำ (ไม่แตะฐานข้อมูล)

    แทน is_tables.build() เดิมที่เขียนลง sqlite — repo นี้ไม่มีฐานข้อมูล ปลายทางคือ JSON
    ลำดับการเรียกต้องเป็นแบบนี้: roster -> desc -> projects -> split -> match
    (match_projects_to_rooms แก้ roster in-place แล้วเติม key "projects" ให้ทุกห้อง)

    ยก RosterNotFoundError ถ้ายังไม่มีไฟล์บัญชีจัดครูเข้าสอน — ผู้เรียกต้องไม่เขียน JSON ทับ
    ของเดิมด้วยข้อมูลว่าง (ไฟล์อาจหายชั่วคราวระหว่าง sync)
    """
    roster = read_roster(files_dir)
    desc = read_desc_status(files_dir)
    extracted = extract_projects(files_dir)
    for rec in extracted:
        split_glued_members(rec)
    match_projects_to_rooms(roster, extracted)
    for row in roster:
        code = row["course_code"]
        # ม.2/ม.5 เรียน IS เดี่ยว (I20201/I30201) ไม่มีคำอธิบายรายวิชาบูรณาการ -> 'na'
        row["desc_status"] = desc.get(code, "na" if code.startswith("I") else "absent")
        row["note"] = NOTES.get(row["room"], "")
        row["submitted"] = bool(row["projects"])
    return roster


__all__ = [
    "RosterNotFoundError",
    "build_roster",
    "extract_projects",
    "match_projects_to_rooms",
    "norm_room",
    "read_desc_status",
    "read_roster",
    "split_glued_members",
]
