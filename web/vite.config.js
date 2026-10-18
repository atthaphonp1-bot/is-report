import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// base: './' — Pages เสิร์ฟเว็บนี้ใต้ subpath (/is-report/) ถ้า build ด้วย base '/' ค่า default
// ไฟล์ js/css จะถูกอ้างเป็น /assets/... แล้ว 404 ทั้งหน้า path แบบ relative ใช้ได้ทั้งบน Pages
// และตอนเปิด dev ที่ localhost โดยไม่ต้องรู้ชื่อ repo
export default defineConfig({
  base: './',
  plugins: [react()],
  server: { host: true, port: 5174 },
})
