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

## ปุ่ม "อัปเดตข้อมูล" ในหน้าเว็บ

หน้าเว็บเป็นไฟล์ static จึงเก็บความลับไม่ได้ ผู้ดูแลต้องกรอก **fine-grained PAT** ของตัวเอง
ครั้งเดียว (เก็บใน localStorage ของ browser ตัวเอง ไม่ได้ฝังในโค้ด) สร้างที่
Settings -> Developer settings -> Personal access tokens -> Fine-grained tokens โดย

- Repository access: เฉพาะ `is-report`
- Permissions: **Actions = Read and write** อย่างเดียวเท่านั้น

ห้ามใช้ classic PAT เพราะสิทธิ์กว้างเกินไป ครูทั่วไปที่ไม่มี token ยังดูรายงานได้ปกติ กดปุ่มไม่ได้เท่านั้น

## ไฟล์บัญชีจัดครูเข้าสอน (ยังค้างอยู่)

`รายชื่อครู_รายวิชา_IS_เทอม1.xlsx` เป็นแกนของรายงาน (กำหนดว่ามีห้องอะไร ครูใครสอน) แต่
**ไม่ได้อยู่ในโฟลเดอร์ Drive ที่ครูส่งงานเข้ามา** ถ้า CI หาไฟล์นี้ไม่เจอ จะข้ามรอบนั้นไปเฉย ๆ
(ไม่เขียนทับข้อมูลเดิมด้วยของว่าง) เลือกทางใดทางหนึ่ง:

1. **อัปโหลดเข้าโฟลเดอร์ Drive เดิม** — ดีที่สุด ไม่ต้อง commit อะไร อัปเดตเทอมหน้าก็แค่เปลี่ยนไฟล์ใน Drive
2. **วางไว้ที่ `sync/inputs/`** แล้ว commit — ลบบรรทัด `sync/inputs/*` ใน `.gitignore` ออกก่อน
   (ไฟล์นี้ไม่มีชื่อนักเรียน มีแต่ห้อง/รหัสวิชา/ชื่อครู แต่ก็เป็นไฟล์ของโรงเรียนที่จะเปิดสาธารณะ)

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
