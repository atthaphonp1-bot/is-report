// ที่เดียวที่รู้ว่า repo นี้คืออะไร — ปุ่มอัปเดตกับลิงก์ไปหน้า Actions อ่านจากที่นี่
// ย้าย repo หรือเปลี่ยนชื่อ แก้แค่ไฟล์นี้
export const GITHUB_OWNER = 'atthaphonp1-bot'
export const GITHUB_REPO = 'is-report'
export const SYNC_WORKFLOW = 'sync.yml'

export const ACTIONS_URL =
  `https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${SYNC_WORKFLOW}`


// ไฟล์ข้อมูลที่ workflow เขียนทับทุกรอบ — path relative เพื่อให้ทำงานได้ทั้งตอน dev
// (localhost:5174/) และตอนอยู่บน Pages ใต้ subpath (/is-report/)
export const REPORT_URL = 'data/report.json'
