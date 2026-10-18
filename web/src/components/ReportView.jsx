// ReportView — หน้า "รายงานสรุป" งาน IS ทั้งโรงเรียน
//
// เดิมหน้านี้ fetch /api/report จาก FastAPI ที่รันบน Mac — ย้ายมาอ่าน data/report.json ที่
// GitHub Actions เขียนทับทุกรอบ sync แทน (ดู .github/workflows/sync.yml) จึงไม่ต้องเปิด
// server ที่เครื่องอีกเลย ไม่มี login เพราะเป็นไฟล์ static ธรรมดาบน Pages
//
// URL ยังเป็น "#report" / "#projects" เหมือนเดิม ลิงก์เก่าที่ครูเก็บไว้จึงยังเปิดถูกแท็บ
import { useEffect, useMemo, useState } from 'react'
import { REPORT_URL } from '../config.js'
import { useCountUp } from '../lib/useCountUp.js'
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

// ตัวเลขเดียวที่ไต่ขึ้นตอนโหลด — ค่าที่เป็นข้อความ (เช่น "37/51") ไม่ไต่ แสดงตรง ๆ
function CountUp({ value }) {
  const animated = useCountUp(typeof value === 'number' ? value : 0)
  return <>{typeof value === 'number' ? animated.toLocaleString('th-TH') : value}</>
}

function StatCard({ label, value, sub, tone = 'neutral' }) {
  // สีใช้บอกสถานะเท่านั้น (ดี/ต้องตาม) ที่เหลือปล่อยเป็นสีตัวอักษรปกติ ให้ขนาดทำหน้าที่เน้นแทน
  const toneClass = tone === 'good' ? 'text-good' : tone === 'warn' ? 'text-warn' : ''
  return (
    <div className="surface min-w-0 p-4 sm:p-5">
      <p className="truncate text-[13px] text-dim">{label}</p>
      <p className={`stat-value mt-1.5 ${toneClass}`}><CountUp value={value} /></p>
      {sub && <p className="mt-1 truncate text-xs text-faint">{sub}</p>}
    </div>
  )
}

function ProgressBar({ done, total }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0
  return (
    <div className="flex items-center gap-2.5">
      <div className="bar-track w-full min-w-0">
        <div
          className="bar-fill"
          style={{
            width: `${pct}%`,
            ...(pct === 100 ? { background: 'var(--good)' } : null),
          }}
        />
      </div>
      <span className="w-9 shrink-0 text-right text-xs tabular-nums text-dim">{pct}%</span>
    </div>
  )
}

function RoomCard({ room, expanded, onToggle }) {
  const teachers = room.teachers.join(' / ')
  return (
    <div className="surface surface-interactive min-w-0">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full min-w-0 items-center gap-3 px-4 py-3.5 text-left sm:px-5"
      >
        <span
          className={`badge shrink-0 ${room.submitted ? 'badge-good' : 'badge-warn'}`}
        >
          {room.room}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{teachers || '—'}</span>
          <span className="mt-0.5 block truncate text-xs text-faint">
            {room.plans.map((p) => p.subject).join(', ')}
          </span>
        </span>
        <span className="shrink-0 text-xs tabular-nums text-dim">
          {room.submitted ? `${room.projects.length} โครงงาน` : 'ยังไม่ส่ง'}
        </span>
        <svg
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
          className={`h-4 w-4 shrink-0 text-faint transition-transform duration-300 ${expanded ? 'rotate-180' : ''}`}
        >
          <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      </button>

      {expanded && (
        <div className="hairline-t rise px-4 pb-4 pt-3 sm:px-5">
          {room.projects.length === 0 ? (
            <p className="text-sm text-faint">ยังไม่ได้ส่งรายชื่อโครงงาน</p>
          ) : (
            <ol className="space-y-2">
              {room.projects.map((p) => (
                <li
                  key={p.ord}
                  className="min-w-0 rounded-2xl px-3.5 py-2.5"
                  style={{ background: 'var(--surface-sunken)' }}
                >
                  <p className="text-sm font-medium">
                    {p.ord}. {p.name}
                  </p>
                  <p className="mt-0.5 text-xs text-dim">
                    {p.member_count} คน
                    {p.advisor ? ` · ที่ปรึกษา ${p.advisor}` : ''}
                  </p>
                  {p.members && (
                    <p className="mt-1.5 break-words text-xs leading-relaxed text-faint">{p.members}</p>
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
    return <p className="py-6 text-sm text-warn">{error}</p>
  }

  if (!data) {
    return (
      <div className="space-y-3 py-6">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="h-20 animate-pulse rounded-[1.25rem]"
            style={{ background: 'var(--surface-sunken)' }}
          />
        ))}
      </div>
    )
  }

  const { summary, grades } = data
  const syncedAt = formatSyncTime(summary.last_synced_at)
  const pending = summary.rooms - summary.submitted

  return (
    <div className="min-w-0 space-y-5 py-6 sm:py-8">
      <div className="rise">
        <h2 className="text-[28px] font-semibold leading-tight tracking-tight sm:text-[34px]">
          รายงานสรุปงาน IS ทั้งโรงเรียน
        </h2>
        <p className="mt-1.5 text-[13px] text-faint">
          {syncedAt ? `ข้อมูลล่าสุดจาก Google Drive เมื่อ ${syncedAt}` : 'ยังไม่เคยซิงก์จาก Drive'}
          {data.includes_members && ' · แสดงรายชื่อสมาชิกโครงงานด้วย'}
        </p>
      </div>

      <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
        <div role="tablist" className="seg flex max-w-full gap-0.5">
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
              className="seg-item"
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
            className="btn-quiet"
          >
            {linkCopied ? 'คัดลอกลิงก์แล้ว' : 'คัดลอกลิงก์หน้านี้'}
          </button>
        </div>
      </div>

      {tab === 'projects' ? (
        <ProjectsView data={data} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
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

          <div className="surface p-4 sm:p-5">
            <h3 className="mb-4 text-sm font-semibold">แยกตามระดับชั้น</h3>
            <ul className="space-y-3.5">
              {grades.map((g) => (
                <li key={g.grade} className="flex min-w-0 items-center gap-3">
                  <span className="w-10 shrink-0 text-sm font-medium">{g.grade}</span>
                  <span className="min-w-0 flex-1">
                    <ProgressBar done={g.submitted} total={g.rooms} />
                  </span>
                  <span className="shrink-0 text-xs tabular-nums text-faint">
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
              className="pill cursor-pointer appearance-none pr-7"
              style={{
                backgroundImage:
                  "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236e6e73' stroke-width='2.5' stroke-linecap='round'><path d='M6 9l6 6 6-6'/></svg>\")",
                backgroundRepeat: 'no-repeat',
                backgroundPosition: 'right 0.7rem center',
              }}
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
              className="pill pill-warn"
              data-active={onlyPending}
            >
              เฉพาะห้องที่ยังไม่ส่ง
            </button>
            <span className="text-xs text-faint">{rooms.length} ห้อง</span>
          </div>

          <div className="space-y-2">
            {rooms.length === 0 ? (
              <p className="rounded-[1.25rem] border border-dashed p-8 text-center text-sm text-faint"
                 style={{ borderColor: 'var(--hairline)' }}>
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
