// รวมคำเตือน "นักเรียนชื่อซ้ำ" ที่เรียงมาจาก report.json ให้เป็นกลุ่มต่อห้อง
//
// sync/dup_check.py เรียงรายการมาตามห้องแล้ว (room, ลำดับโครงงานแรก, ชื่อ) ที่นี่แค่ยุบ
// รายการที่ห้องเดียวกันติดกันให้เป็นก้อนเดียว เพื่อให้แสดงหัวข้อห้องครั้งเดียวต่อห้อง
// แยกออกมาจากคอมโพเนนต์เพื่อเทสได้ด้วย node --test (ดู groupDuplicates.test.js)
export function groupDuplicatesByRoom(warnings) {
  const out = []
  for (const w of warnings || []) {
    const last = out[out.length - 1]
    if (last && last.room === w.room) last.items.push(w)
    else out.push({ room: w.room, items: [w] })
  }
  return out
}
