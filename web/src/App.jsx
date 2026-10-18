// App — เปลือกของหน้ารายงานงาน IS บน GitHub Pages
//
// เบากว่าของเดิมมาก เพราะไม่มี login / แชท / หน้า admin อีกแล้ว (ดู docs ของ repo เดิม
// ถ้าต้องการโค้ดส่วนนั้น) เหลือแค่ header + ReportView ที่อ่าน data/report.json
// แท็บอยู่ใน ReportView และผูกกับ hash #report / #projects เองตามเดิม
import ReportView from './components/ReportView.jsx'
import { ACTIONS_URL } from './config.js'

export default function App() {
  return (
    <div className="min-h-screen bg-neutral-50 font-sans text-neutral-800">
      <header className="sticky top-0 z-10 border-b border-neutral-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-3 px-3 py-2.5 sm:px-4">
          <h1 className="min-w-0 truncate text-sm font-semibold sm:text-base">
            รายงานงาน IS โรงเรียน
          </h1>
          <a
            href={ACTIONS_URL}
            target="_blank"
            rel="noreferrer"
            className="shrink-0 text-xs text-neutral-400 hover:text-accent-600"
          >
            ประวัติการอัปเดต
          </a>
        </div>
      </header>
      <main className="mx-auto max-w-4xl">
        <ReportView />
      </main>
      <footer className="mx-auto max-w-4xl px-4 pb-8 pt-2 text-xs text-neutral-400">
        ข้อมูลมาจาก Google Drive ของกลุ่มงาน IS · อัปเดตอัตโนมัติทุก 30 นาที
      </footer>
    </div>
  )
}
