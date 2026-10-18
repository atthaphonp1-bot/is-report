# is-report — รายงานงาน IS โรงเรียน

หน้าเว็บสรุปสถานะงาน IS (ห้องไหนส่ง/ยังไม่ส่ง ครูคนไหนต้องตามงาน โครงงานรายห้อง)
อยู่บน GitHub Pages ไม่ต้องเปิด server ที่เครื่องไหนเลย

| ใช้ทำอะไร | ลิงก์ |
|---|---|
| ติดตามการส่ง | https://atthaphonp1-bot.github.io/is-report/#report |
| โครงงานรายห้อง (มีช่องค้นหา) | https://atthaphonp1-bot.github.io/is-report/#projects |
| สั่งอัปเดตเอง / ดูประวัติ | https://github.com/atthaphonp1-bot/is-report/actions/workflows/sync.yml |

## ข้อมูลอัปเดตยังไง

```
Google Drive (ครูส่งไฟล์เข้าโฟลเดอร์)
   │   GitHub Actions: cron ทุก 30 นาที จ-ศ 07:00-18:00
   │   หรือกดปุ่ม "อัปเดตข้อมูล" ในหน้าเว็บ
   v
sync/export_report.py  ->  web/public/data/report.json  ->  commit  ->  deploy Pages
```

## ข้อมูลอะไรบ้างที่เปิดเผย

repo นี้เป็น public (GitHub Pages ฟรีได้เฉพาะ public) และรายงาน **รวมชื่อ-นามสกุลของนักเรียน
เจ้าของโครงงานด้วย** นอกเหนือจากชื่อห้อง ชื่อครู ชื่อรายวิชา ชื่อโครงงาน และจำนวนสมาชิก

เจ้าของโปรเจกต์ตัดสินใจเรื่องนี้เองเมื่อ 2026-10-18 โดยรับทราบแล้วว่าหน้าเว็บสาธารณะต่างจาก
การจัดแสดงในโรงเรียน: เสิร์ชเอนจินเก็บ index ได้ บริการอย่าง Wayback Machine เก็บสำเนาถาวรได้
ใครก็ก๊อปไปทั้งก้อนได้ และลบทีหลังก็เรียกคืนสำเนาที่กระจายไปแล้วไม่ได้ เหตุผลที่เลือกคือโครงงาน
เหล่านี้จัดแสดงเปิดเผยอยู่แล้ว

**ถ้าต้องการกลับไปซ่อนชื่อนักเรียน** แก้ `sync/report_shape.py` ให้ไม่ใส่คีย์ `members` ลงใน
dict ของแต่ละโครงงาน แล้วตั้ง `includes_members` เป็น `False` หน้าเว็บรองรับโหมดนั้นอยู่แล้ว
(ทั้ง `ReportView.jsx` และ `ProjectsView.jsx` เช็ค `p.members` ก่อนแสดง) แต่สำเนาที่ถูก index
หรือก๊อปไปก่อนหน้านั้นจะยังอยู่

## ต้องตั้งค่าอะไรบ้าง

Secrets ของ repo (Settings -> Secrets and variables -> Actions):

| ชื่อ | ค่า |
|---|---|
| `GDRIVE_SA_JSON` | เนื้อไฟล์ service account ของ Google ทั้งก้อน (ต้องแชร์โฟลเดอร์ Drive ให้อีเมลของ service account แบบอ่านอย่างเดียว) |
| `GDRIVE_FOLDER_ID` | id ของโฟลเดอร์ Drive ที่ครูส่งงานเข้ามา |

Pages: Settings -> Pages -> Source = **GitHub Actions**

## อัปเดตข้อมูลเมื่อไหร่

workflow รันเองทุก 30 นาที วันจันทร์-ศุกร์ 07:00-18:00 (เวลาไทย) หน้าเว็บจึงไม่มีปุ่มอะไรให้กด
ผู้ใช้แค่เปิดดู

อยากอัปเดตเดี๋ยวนั้น: เปิด
[หน้า Actions](https://github.com/atthaphonp1-bot/is-report/actions/workflows/sync.yml)
(ลิงก์ "ประวัติการอัปเดต" มุมขวาบนของหน้าเว็บก็พามาที่นี่) แล้วกด **Run workflow** —
ต้องล็อกอิน GitHub ที่มีสิทธิ์เขียน repo นี้

> เคยมีปุ่ม "อัปเดตข้อมูล" ในหน้าเว็บที่สั่ง workflow ผ่าน GitHub REST API แต่ถอดออกเมื่อ
> 2026-10-18 เพราะหน้า static เก็บความลับไม่ได้ ผู้ดูแลจึงต้องกรอก personal access token
> ของตัวเองก่อนใช้งาน ซึ่งยุ่งยากเกินความจำเป็นในเมื่อ cron ทำงานให้อยู่แล้ว
> ดู `git log` คำว่า "UpdateButton" ถ้าอยากได้โค้ดส่วนนั้นกลับมา

## ไฟล์บัญชีจัดครูเข้าสอน

`sync/inputs/รายชื่อครู_รายวิชา_IS_เทอม1.xlsx` คือแกนของรายงาน — กำหนดว่ามีห้องอะไร
แผนการเรียนไหน ครูใครสอน ห้องที่ไม่มีในไฟล์นี้จะไม่ขึ้นในรายงานเลย

ไฟล์นี้ **ไม่ได้อยู่ในโฟลเดอร์ Drive** ที่ครูส่งงานเข้ามา จึง commit ไว้ใน repo แทน
`export_report.py` จะ copy ทุกไฟล์ใน `sync/inputs/` ลงไปรวมกับไฟล์ที่โหลดจาก Drive ก่อน parse
โดยไฟล์จาก Drive ทับไฟล์ในนี้ — ถ้าวันหนึ่งอัปโหลดไฟล์ชื่อเดียวกันเข้า Drive ระบบจะใช้ของใน
Drive ให้เองโดยไม่ต้องแก้โค้ด

**ขึ้นเทอมใหม่ต้องเปลี่ยนไฟล์นี้** วางไฟล์ใหม่ทับแล้ว commit (หรืออัปโหลดเข้า Drive)
ถ้า CI หาไฟล์ไม่เจอจะข้ามรอบนั้นไปเฉย ๆ พร้อม warning ไม่เขียนทับข้อมูลเดิมด้วยของว่าง

## รันเองในเครื่อง

```bash
pip install -r sync/requirements.txt
export GDRIVE_FOLDER_ID=...  GDRIVE_SA_JSON="$(cat ~/.config/is-agent/sa.json)"
python -m sync.export_report --out web/public/data/report.json
cd web && npm install && npm run dev
pytest sync/ -q
```

โค้ด parse ไฟล์ครู (`sync/parse_is.py`) และตัวอ่าน Drive (`sync/drive.py`) พอร์ตมาจากโปรเจกต์เดิม
(RAG + agent ที่รันด้วย Ollama บน Mac) ตัดส่วนที่ผูกกับ SQLite/Ollama ออกทั้งหมด
