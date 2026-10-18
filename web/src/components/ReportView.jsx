// ReportView — หน้า "รายงานสรุป" งาน IS ทั้งโรงเรียน
//
// เดิมหน้านี้ fetch /api/report จาก FastAPI ที่รันบน Mac — ย้ายมาอ่าน data/report.json ที่
// GitHub Actions เขียนทับทุกรอบ sync แทน (ดู .github/workflows/sync.yml) จึงไม่ต้องเปิด
// server ที่เครื่องอีกเลย ไม่มี login เพราะเป็นไฟล์ static ธรรมดาบน Pages
//
// URL ยังเป็น "#report" / "#projects" เหมือนเดิม ลิงก์เก่าที่ครูเก็บไว้จึงยังเปิดถูกแท็บ
import { useEffect, useMemo, useState } from 'react'
import { REPORT_URL } from '../config.js'
import ProjectsView from './ProjectsView.jsx'
import UpdateButton from './UpdateButton.jsx'

function formatSyncTime(ts) {
  if (!ts) return null
  try {
    return new Date(ts).toLocaleString('th-TH', {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return ts
  }
}

function StatCard({ label, value, sub, tone = 'neutral' }) {
  const toneClass =
    tone === 'good'
      ? 'text-emerald-600'
      : tone === 'warn'
        ? 'text-amber-600'
        : 'text-neutral-800'
  return (
    <div className="min-w-0 rounded-2xl border border-neutral-200 bg-white p-3 shadow-sm sm:p-4">
      <p className="truncate text-xs text-neutral-500">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${toneClass}`}>{value}</p>
      {sub && <p className="mt-0.5 truncate text-xs text-neutral-400">{sub}</p>}
    </div>
  )
}

function ProgressBar({ done, total }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-full min-w-0 overflow-hidden rounded-full bg-neutral-200">
        <div
          className={`h-full rounded-full ${pct === 100 ? 'bg-emerald-500' : 'bg-accent-600'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="shrink-0 text-xs tabular-nums text-neutral-500">{pct}%</span>
    </div>
  )
}

function RoomCard({ room, expanded, onToggle }) {
  const teachers = room.teachers.join(' / ')
  return (
    <div className="min-w-0 rounded-2xl border border-neutral-200 bg-white shadow-sm">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full min-w-0 items-center gap-3 px-3 py-2.5 text-left sm:px-4"
      >
        <span
          className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${
            room.submitted
              ? 'bg-emerald-50 text-emerald-700'
              : 'bg-amber-50 text-amber-700'
          }`}
        >
          {room.room}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm text-neutral-700">{teachers || '—'}</span>
          <span className="block truncate text-xs text-neutral-400">
            {room.plans.map((p) => p.subject).join(', ')}
          </span>
        </span>
        <span className="shrink-0 text-xs tabular-nums text-neutral-500">
          {room.submitted ? `${room.projects.length} โครงงาน` : 'ยังไม่ส่ง'}
        </span>
        <svg
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
          className={`h-4 w-4 shrink-0 text-neutral-300 transition-transform ${expanded ? 'rotate-180' : ''}`}
        >
          <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      </button>

      {expanded && (
        <div className="border-t border-neutral-100 px-3 pb-3 pt-2 sm:px-4">
          {room.projects.length === 0 ? (
            <p className="text-sm text-neutral-400">ยังไม่ได้ส่งรายชื่อโครงงาน</p>
          ) : (
            <ol className="space-y-2">
              {room.projects.map((p) => (
                <li key={p.ord} className="min-w-0 rounded-xl bg-neutral-50 px-3 py-2">
                  <p className="text-sm font-medium text-neutral-800">
                    {p.ord}. {p.name}
                  </p>
                  <p className="mt-0.5 text-xs text-neutral-500">
                    {p.member_count} คน
                    {p.advisor ? ` · ที่ปรึกษา ${p.advisor}` : ''}
                  </p>
                  {p.members && (
                    <p className="mt-1 break-words text-xs text-neutral-400">{p.members}</p>
                  )}
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  )
}

export default function ReportView() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [gradeFilter, setGradeFilter] = useState('all')
  const [onlyPending, setOnlyPending] = useState(false)
  const [expanded, setExpanded] = useState(() => new Set())
  // แท็บผูกกับ hash ให้ก็อปลิงก์ส่งต่อได้ทั้งสองแท็บ: #report / #projects (ผู้ใช้ขอลิงก์
  // "โครงงาน_IS_รายห้อง_เทอม1-2569" แบบเดียวกับหน้าติดตาม 2026-09-13)
  const [tab, setTab] = useState(() =>
    window.location.hash === '#projects' ? 'projects' : 'tracking',
  )
  const [linkCopied, setLinkCopied] = useState(false)

  useEffect(() => {
    const onHashChange = () =>
      setTab(window.location.hash === '#projects' ? 'projects' : 'tracking')
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  function selectTab(next) {
    setTab(next)
    setLinkCopied(false)
    window.history.replaceState(null, '', next === 'projects' ? '#projects' : '#report')
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href)
      setLinkCopied(true)
    } catch {
      setLinkCopied(false)
    }
  }

  // reloadAt เปลี่ยนค่า = สั่งโหลดไฟล์ใหม่ (ปุ่มอัปเดตเรียกหลัง workflow ทำงานเสร็จ)
  const [reloadAt, setReloadAt] = useState(0)

  useEffect(() => {
    let cancelled = false
    // ต่อ query เวลาไว้กัน cache ของ GitHub Pages ส่งไฟล์เก่ากลับมาหลังเพิ่ง sync เสร็จ
    fetch(`${REPORT_URL}?t=${reloadAt}`, { cache: 'no-store' })
      .then((res) => {
        if (!res.ok) throw new Error(`โหลดรายงานไม่สำเร็จ (${res.status})`)
        return res.json()
      })
      .then((payload) => {
        if (!cancelled) {
          setData(payload)
          setError(null)
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [reloadAt])

  const rooms = useMemo(() => {
    if (!data) return []
    return data.rooms.filter(
      (r) =>
        (gradeFilter === 'all' || r.grade === gradeFilter) && (!onlyPending || !r.submitted),
    )
  }, [data, gradeFilter, onlyPending])

  function toggle(room) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(room)) next.delete(room)
      else next.add(room)
      return next
    })
  }

  if (error) {
    return <p className="p-4 text-sm text-red-600">{error}</p>
  }

  if (!data) {
    return (
      <div className="space-y-3 p-4">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-16 animate-pulse rounded-2xl bg-neutral-100" />
        ))}
      </div>
    )
  }

  const { summary, grades } = data
  const syncedAt = formatSyncTime(summary.last_synced_at)
  const pending = summary.rooms - summary.submitted

  return (
    <div className="min-w-0 space-y-4 p-3 sm:p-4">
      <div>
        <h2 className="text-lg font-semibold text-neutral-800">
          รายงานสรุปงาน IS ทั้งโรงเรียน
        </h2>
        <p className="mt-0.5 text-xs text-neutral-400">
          {syncedAt ? `ข้อมูลล่าสุดจาก Google Drive เมื่อ ${syncedAt}` : 'ยังไม่เคยซิงก์จาก Drive'}
          {data.includes_members && ' · แสดงรายชื่อสมาชิกโครงงานด้วย'}
        </p>
      </div>

      <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
        <div role="tablist" className="flex max-w-full gap-1 rounded-full bg-neutral-100 p-1">
          {[
            ['tracking', 'ติดตามการส่ง'],
            ['projects', 'โครงงานรายห้อง'],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={tab === key}
              onClick={() => selectTab(key)}
              className={`whitespace-nowrap rounded-full px-3 py-1 text-xs font-medium transition-colors sm:text-sm ${
                tab === key ? 'bg-white text-neutral-800 shadow-sm' : 'text-neutral-500'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <UpdateButton onDone={() => setReloadAt(Date.now())} />
          <button
            type="button"
            onClick={copyLink}
            className="rounded-full px-3 py-1 text-xs font-medium text-accent-600 hover:bg-accent-100"
          >
            {linkCopied ? 'คัดลอกลิงก์แล้ว' : 'คัดลอกลิงก์หน้านี้'}
          </button>
        </div>
      </div>

      {tab === 'projects' ? (
        <ProjectsView data={data} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 sm:gap-3 lg:grid-cols-4">
            <StatCard
              label="ส่งรายชื่อโครงงานแล้ว"
              value={`${summary.submitted}/${summary.rooms}`}
              sub="ห้อง"
              tone="good"
            />
            <StatCard label="ยังไม่ส่ง" value={pending} sub="ห้อง" tone={pending ? 'warn' : 'good'} />
            <StatCard label="โครงงานทั้งหมด" value={summary.projects} sub="โครงงาน" />
            <StatCard label="นักเรียน" value={summary.students} sub={`ครู ${summary.teachers} คน`} />
          </div>

          <div className="rounded-2xl border border-neutral-200 bg-white p-3 shadow-sm sm:p-4">
            <h3 className="mb-3 text-sm font-semibold text-neutral-700">แยกตามระดับชั้น</h3>
            <ul className="space-y-2.5">
              {grades.map((g) => (
                <li key={g.grade} className="flex min-w-0 items-center gap-3">
                  <span className="w-10 shrink-0 text-sm font-medium text-neutral-700">{g.grade}</span>
                  <span className="min-w-0 flex-1">
                    <ProgressBar done={g.submitted} total={g.rooms} />
                  </span>
                  <span className="shrink-0 text-xs tabular-nums text-neutral-500">
                    {g.submitted}/{g.rooms} ห้อง · {g.projects} โครงงาน
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <select
              value={gradeFilter}
              onChange={(e) => setGradeFilter(e.target.value)}
              className="rounded-full border border-neutral-200 bg-white px-3 py-1.5 text-xs text-neutral-700"
              aria-label="กรองตามระดับชั้น"
            >
              <option value="all">ทุกระดับชั้น</option>
              {grades.map((g) => (
                <option key={g.grade} value={g.grade}>
                  {g.grade}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => setOnlyPending((v) => !v)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                onlyPending
                  ? 'bg-amber-500 text-white'
                  : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
              }`}
            >
              เฉพาะห้องที่ยังไม่ส่ง
            </button>
            <span className="text-xs text-neutral-400">{rooms.length} ห้อง</span>
          </div>

          <div className="space-y-2">
            {rooms.length === 0 ? (
              <p className="rounded-2xl border border-dashed border-neutral-200 p-6 text-center text-sm text-neutral-400">
                ไม่มีห้องที่ตรงกับตัวกรอง
              </p>
            ) : (
              rooms.map((room) => (
                <RoomCard
                  key={room.room}
                  room={room}
                  expanded={expanded.has(room.room)}
                  onToggle={() => toggle(room.room)}
                />
              ))
            )}
          </div>        </>
      )}
    </div>
  )
}
