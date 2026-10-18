// ProjectsView — แท็บ "โครงงานรายห้อง" ในหน้ารายงานสรุป (2026-09-13)
//
// ผู้ใช้ขอลิงก์ "โครงงาน_IS_รายห้อง_เทอม1-2569" แบบเดียวกับหน้าติดตามการส่งงาน (#report) — เดิมเป็น
// ไฟล์ HTML ใน reports/ ที่ generate ครั้งเดียวเมื่อ 8 ก.ย. ตัวเลขเก่าไปแล้ว (ตอนนั้น 225 โครงงาน
// ตอนนี้ 278) หน้านี้ใช้ข้อมูลชุดเดียวกับ ReportView (data/report.json ที่ GitHub Actions เขียน)
//
// จุดเด่นของไฟล์เดิมที่ต้องคงไว้คือช่องค้นหา — ค้นได้ทั้งห้อง ครู วิชา ชื่อโครงงาน และชื่อนักเรียน
// (ดู lib/filterRooms.js)
import { useMemo, useState } from 'react'
import { filterRooms } from '../lib/filterRooms.js'

function RoomProjects({ room }) {
  const subjects = [...new Set(room.plans.map((p) => p.subject).filter(Boolean))].join(', ')
  return (
    <section className="min-w-0 rounded-2xl border border-neutral-200 bg-white p-3 shadow-sm sm:p-4">
      <div className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <h3 className="text-base font-semibold text-neutral-800">{room.room}</h3>
        <span className="min-w-0 text-sm text-neutral-600">{subjects || '—'}</span>
      </div>
      <p className="mt-0.5 break-words text-xs text-neutral-500">
        ครูผู้สอน {room.teachers.join(' / ') || '—'} · {room.projects.length} โครงงาน
      </p>

      <ol className="mt-2 space-y-1.5">
        {room.projects.map((p) => (
          <li key={p.ord} className="min-w-0 rounded-xl bg-neutral-50 px-3 py-2">
            <p className="break-words text-sm font-medium text-neutral-800">
              {p.ord}. {p.name}
            </p>
            <p className="mt-0.5 text-xs text-neutral-500">
              {p.member_count} คน
              {p.advisor ? ` · ที่ปรึกษา ${p.advisor}` : ''}
            </p>
            {p.members && <p className="mt-1 break-words text-xs text-neutral-400">{p.members}</p>}
          </li>
        ))}
      </ol>
    </section>
  )
}

export default function ProjectsView({ data }) {
  const [query, setQuery] = useState('')
  const [grade, setGrade] = useState('all')

  const gradeRooms = useMemo(
    () => data.rooms.filter((r) => grade === 'all' || r.grade === grade),
    [data, grade],
  )
  const matched = useMemo(() => filterRooms(gradeRooms, query), [gradeRooms, query])
  const submitted = matched.filter((r) => r.projects.length > 0)
  const pending = matched.filter((r) => r.projects.length === 0)
  const projectCount = submitted.reduce((n, r) => n + r.projects.length, 0)

  return (
    <div className="min-w-0 space-y-3">
      <div className="space-y-2">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={
            data.includes_members
              ? 'ค้นหาห้อง ครู วิชา ชื่อโครงงาน หรือชื่อนักเรียน'
              : 'ค้นหาห้อง ครู วิชา หรือชื่อโครงงาน'
          }
          aria-label="ค้นหาโครงงาน"
          className="w-full min-w-0 rounded-full border border-neutral-200 bg-white px-4 py-2 text-sm text-neutral-800 focus:border-accent-600 focus:outline-none"
        />
        <div className="flex min-w-0 flex-wrap items-center gap-1.5">
          {['all', ...data.grades.map((g) => g.grade)].map((g) => (
            <button
              key={g}
              type="button"
              onClick={() => setGrade(g)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                grade === g
                  ? 'bg-accent-600 text-white'
                  : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
              }`}
            >
              {g === 'all' ? 'ทุกชั้น' : g}
            </button>
          ))}
          <span className="ml-1 text-xs text-neutral-400">
            พบ {submitted.length} ห้อง · {projectCount} โครงงาน
          </span>
        </div>
      </div>

      {submitted.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-neutral-200 p-6 text-center text-sm text-neutral-400">
          ไม่พบโครงงานที่ตรงกับคำค้น
        </p>
      ) : (
        <div className="space-y-2">
          {submitted.map((room) => (
            <RoomProjects key={room.room} room={room} />
          ))}
        </div>
      )}

      {pending.length > 0 && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 sm:p-4">
          <h3 className="text-sm font-semibold text-amber-800">
            ห้องที่ยังไม่ส่งรายชื่อโครงงาน ({pending.length} ห้อง)
          </h3>
          <ul className="mt-1.5 space-y-0.5">
            {pending.map((r) => (
              <li key={r.room} className="break-words text-xs text-amber-800">
                {r.room} — {r.teachers.join(' / ') || '—'}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
