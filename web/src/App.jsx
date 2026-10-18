// App — เปลือกของหน้ารายงานงาน IS บน GitHub Pages
//
// เบากว่าของเดิมมาก เพราะไม่มี login / แชท / หน้า admin อีกแล้ว (ดู repo เดิมถ้าต้องการโค้ด
// ส่วนนั้น) เหลือแค่ header + ReportView ที่อ่าน data/report.json
// แท็บอยู่ใน ReportView และผูกกับ hash #report / #projects เองตามเดิม
import ReportView from './components/ReportView.jsx'
import { ACTIONS_URL } from './config.js'

export default function App() {
  return (
    <div className="min-h-screen">
      {/* header โปร่งแสง เบลอพื้นหลังที่เลื่อนผ่านข้างใต้ — เส้นคั่นบางที่สุดเท่าที่ยังเห็น */}
      <header
        className="sticky top-0 z-20 border-b"
        style={{
          borderColor: 'var(--hairline)',
          background: 'color-mix(in srgb, var(--bg) 72%, transparent)',
          backdropFilter: 'saturate(180%) blur(20px)',
          WebkitBackdropFilter: 'saturate(180%) blur(20px)',
        }}
      >
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <h1 className="min-w-0 truncate text-[15px] font-semibold tracking-tight sm:text-base">
            รายงานงาน IS
          </h1>
          <a
            href={ACTIONS_URL}
            target="_blank"
            rel="noreferrer"
            className="shrink-0 text-xs text-faint transition-colors hover:text-accent"
          >
            ประวัติการอัปเดต
          </a>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 sm:px-6">
        <ReportView />
      </main>

      <footer className="mx-auto max-w-5xl px-4 pb-12 pt-4 text-xs text-faint sm:px-6">
        ข้อมูลมาจาก Google Drive ของกลุ่มงาน IS · อัปเดตอัตโนมัติทุก 30 นาที
      </footer>
    </div>
  )
}
