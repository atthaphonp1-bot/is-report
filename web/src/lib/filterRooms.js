// filterRooms — กรองห้องในหน้า "โครงงานรายห้อง" ตามคำค้น (2026-09-13)
//
// ค้นได้ทุกอย่างที่ครูมักพิมพ์หา: เลขห้อง/ชั้น, ชื่อครู, ชื่อวิชา/รหัสวิชา, ชื่อโครงงาน, ครูที่ปรึกษา,
// ชื่อนักเรียน — พิมพ์หลายคำคั่นด้วยช่องว่างได้ ห้องต้องมีครบ "ทุกคำ" ถึงจะแสดง (เช่น "ม.2 สบู่")
// ไม่สนตัวพิมพ์เล็ก/ใหญ่ (รหัสวิชา "I20201" พิมพ์ "i20201" ก็เจอ) และช่องว่างซ้อนจากคีย์บอร์ดมือถือ
//
// ที่มา: ร่างโดย llm-orchestrator (dispatch_subtask, ผู้ใช้ขอให้ใช้ orchestrator จัดงาน) ด้วยข้อมูล
// ตัวอย่างชื่อสมมติ แล้วตรวจจริงด้วย node กับ 12 กรณี + ตรวจว่าไม่แก้ไข input ผ่านครบ
// แก้เองหลังรับมา 1 จุด: ตัวแปร loop `t` ถูกประกาศซ้ำ 2 ครั้ง (ESLint no-redeclare) เปลี่ยนตัวหลังเป็น `k`
//
// ค่า null/undefined ถูกข้าม ห้ามกลายเป็นคำว่า "null" ในข้อความค้น (ไม่งั้นพิมพ์ "null" แล้วเจอทุกห้อง
// ที่ไม่มีครูที่ปรึกษา)

export function filterRooms(rooms, query) {
  // 1. Normalize query
  var q = query == null ? '' : String(query)
  q = q.trim().replace(/\s+/g, ' ').toLowerCase()

  // 2. Empty query returns a shallow copy of the original array
  if (q === '') {
    return rooms.slice()
  }

  // 3. Split into terms
  var terms = q.split(' ')

  var result = []

  // 4. Single loop over rooms
  for (var i = 0; i < rooms.length; i++) {
    var r = rooms[i]
    var parts = []

    // room and grade
    if (r.room != null) parts.push(r.room)
    if (r.grade != null) parts.push(r.grade)

    // teachers
    if (Array.isArray(r.teachers)) {
      for (var t = 0; t < r.teachers.length; t++) {
        var teacher = r.teachers[t]
        if (teacher != null) parts.push(teacher)
      }
    }

    // plans
    if (Array.isArray(r.plans)) {
      for (var p = 0; p < r.plans.length; p++) {
        var plan = r.plans[p]
        if (plan.subject != null) parts.push(plan.subject)
        if (plan.course_code != null) parts.push(plan.course_code)
      }
    }

    // projects
    if (Array.isArray(r.projects)) {
      for (var pr = 0; pr < r.projects.length; pr++) {
        var proj = r.projects[pr]
        if (proj.name != null) parts.push(proj.name)
        if (proj.advisor != null) parts.push(proj.advisor)
        if (proj.members != null) parts.push(proj.members)
      }
    }

    // Build haystack string
    var haystack = parts.join(' ').toLowerCase()

    // 5. Check all terms
    var allMatch = true
    for (var k = 0; k < terms.length; k++) {
      if (haystack.indexOf(terms[k]) === -1) {
        allMatch = false
        break
      }
    }

    // 6. Add matching room
    if (allMatch) {
      result.push(r)
    }
  }

  return result
}
