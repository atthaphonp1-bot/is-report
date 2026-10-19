// คำเตือน "นักเรียนชื่อซ้ำ" — ผู้ใช้สั่งเมื่อ 2026-10-19 ให้เตือน ไม่ใช่ตัดออกเอง
//
// ต่างจากไฟล์ซ้ำ (docx + pdf ของเนื้อหาเดียวกัน) ที่ sync ตัดอัตโนมัติไปแล้ว: ชื่อเด็กที่อยู่
// เกินหนึ่งโครงงานโปรแกรมไม่รู้ว่ากลุ่มไหนถูก จึงต้องให้ครูเจ้าของห้องเห็นแล้วไปแก้ไฟล์ใน Drive
// ข้อมูลมาจาก data/report.json: warnings.duplicate_students / warnings.cross_room_students
// และธงรายห้อง room.duplicate_students + รายโครงงาน project.duplicate_members (ดู
// sync/dup_check.py)
import { groupDuplicatesByRoom } from '../lib/groupDuplicates.js'

const LEVEL_LABEL = {
  confirmed: 'ชื่อ-นามสกุลตรงกัน',
  likely: 'ชื่อต้นตรงกัน อาจเป็นคนละคน',
}

// แสดงที่หัวการ์ดห้อง ให้ครูเห็นว่าห้องนี้ต้องเข้าไปดูโดยไม่ต้องกางทุกโครงงาน
export function RoomDuplicateBadge({ room }) {
  const n = room.duplicate_students?.length || 0
  if (!n) return null
  return <span className="badge badge-warn shrink-0">ชื่อซ้ำ {n}</span>
}

// แสดงใต้รายชื่อสมาชิกของโครงงานที่มีชื่อซ้ำ
export function ProjectDuplicateNote({ project }) {
  const names = project.duplicate_members
  if (!names?.length) return null
  return (
    <p className="mt-1.5 break-words text-xs font-medium text-warn">
      ชื่อซ้ำในห้องนี้: {names.join(', ')}
    </p>
  )
}

// รายชื่อแบบเต็มในการ์ดห้องที่กางอยู่ — ครูที่เปิดดูห้องตัวเองเห็นว่าใครซ้ำกับโครงงานไหน
export function RoomDuplicateList({ room }) {
  const items = room.duplicate_students
  if (!items?.length) return null
  return (
    <div className="mb-2.5 rounded-2xl px-3.5 py-2.5" style={{ background: 'var(--warn-soft)' }}>
      <p className="text-xs font-semibold text-warn">
        นักเรียนชื่อซ้ำในห้องนี้ {items.length} คน — รบกวนตรวจไฟล์ใน Drive แล้วแก้ที่ต้นทาง
      </p>
      <ul className="mt-1 space-y-0.5">
        {items.map((w) => (
          <li key={w.student} className="break-words text-xs text-warn">
            {w.student} — โครงงาน {w.ords.join(', ')}
            <span className="text-faint"> · {LEVEL_LABEL[w.level] || w.level}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function RoomGroup({ room, items }) {
  return (
    <li className="min-w-0">
      <p className="text-xs font-semibold text-warn">{room}</p>
      <ul className="mt-0.5 space-y-0.5">
        {items.map((w) => (
          <li key={w.student} className="break-words text-xs text-warn">
            {w.student} — อยู่ {w.count} ครั้ง (โครงงาน {w.ords.join(', ')})
            <span className="text-faint"> · {LEVEL_LABEL[w.level] || w.level}</span>
          </li>
        ))}
      </ul>
    </li>
  )
}

export default function DuplicateWarnings({ data }) {
  const inRoom = data.warnings?.duplicate_students || []
  const crossRoom = data.warnings?.cross_room_students || []
  if (inRoom.length === 0 && crossRoom.length === 0) return null

  const byRoom = groupDuplicatesByRoom(inRoom)

  return (
    <div className="rise rounded-[1.25rem] p-4 sm:p-5" style={{ background: 'var(--warn-soft)' }}>
      <h3 className="text-sm font-semibold text-warn">
        ตรวจพบนักเรียนชื่อซ้ำ {inRoom.length} คน
      </h3>
      <p className="mt-1 text-xs text-faint">
        ระบบไม่ตัดออกเอง เพราะไม่รู้ว่าเด็กอยู่กลุ่มไหนจริง — รบกวนครูประจำวิชาตรวจไฟล์ใน Drive
        แล้วแก้ที่ต้นทาง รอบ sync ถัดไปคำเตือนจะหายไปเอง
      </p>
      {byRoom.length > 0 && (
        <ul className="mt-2.5 space-y-2">
          {byRoom.map((g) => (
            <RoomGroup key={g.room} room={g.room} items={g.items} />
          ))}
        </ul>
      )}
      {crossRoom.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-semibold text-warn">ชื่อเดียวกันอยู่หลายห้อง</p>
          <ul className="mt-0.5 space-y-0.5">
            {crossRoom.map((w) => (
              <li key={w.student} className="break-words text-xs text-warn">
                {w.student} — {w.rooms.join(', ')}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
