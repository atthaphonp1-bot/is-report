import assert from 'node:assert/strict'
import test from 'node:test'
import { groupDuplicatesByRoom } from './groupDuplicates.js'

test('ไม่มีคำเตือนได้ลิสต์ว่าง', () => {
  assert.deepEqual(groupDuplicatesByRoom([]), [])
  assert.deepEqual(groupDuplicatesByRoom(undefined), [])
})

test('ยุบรายการห้องเดียวกันเป็นก้อนเดียว', () => {
  const warnings = [
    { room: 'ม.2/5', student: 'ก' },
    { room: 'ม.2/5', student: 'ข' },
    { room: 'ม.3/5', student: 'ค' },
  ]
  assert.deepEqual(groupDuplicatesByRoom(warnings), [
    { room: 'ม.2/5', items: [warnings[0], warnings[1]] },
    { room: 'ม.3/5', items: [warnings[2]] },
  ])
})

test('ห้องเดิมที่ไม่ติดกันไม่ถูกยุบข้ามห้องอื่น', () => {
  const warnings = [{ room: 'A', student: '1' }, { room: 'B', student: '2' }, { room: 'A', student: '3' }]
  assert.deepEqual(
    groupDuplicatesByRoom(warnings).map((g) => g.room),
    ['A', 'B', 'A'],
  )
})
