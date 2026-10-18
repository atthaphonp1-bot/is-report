// เทสเฉพาะส่วน pure ของ useCountUp (easeOutExpo, valueAt) — ตัวฮุคต้องมี React runtime
// จึงตรวจด้วยการเปิดหน้าเว็บจริงแทน
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { easeOutExpo, valueAt } from './useCountUp.js'

describe('easeOutExpo', () => {
  it('อยู่ในช่วง 0..1 เสมอ', () => {
    for (const t of [-5, -0.1, 0, 0.25, 0.5, 0.75, 1, 1.5, 99]) {
      const v = easeOutExpo(t)
      assert.ok(v >= 0 && v <= 1, `t=${t} ได้ ${v}`)
    }
  })
  it('เริ่มที่ 0 จบที่ 1 เป๊ะ', () => {
    assert.equal(easeOutExpo(0), 0)
    assert.equal(easeOutExpo(1), 1)
    assert.equal(easeOutExpo(2), 1)
    assert.equal(easeOutExpo(-1), 0)
  })
  it('ไต่ขึ้นอย่างเดียว ไม่ย้อนกลับ', () => {
    let prev = -1
    for (let t = 0; t <= 1.0001; t += 0.05) {
      const v = easeOutExpo(t)
      assert.ok(v >= prev, `ย้อนกลับที่ t=${t}`)
      prev = v
    }
  })
  it('ช่วงแรกขยับเร็วกว่าช่วงท้าย (ซึ่งคือจุดประสงค์ของ ease-out)', () => {
    assert.ok(easeOutExpo(0.2) - easeOutExpo(0) > easeOutExpo(1) - easeOutExpo(0.8))
  })
})

describe('valueAt', () => {
  it('ถึงเวลาแล้วได้ค่าเป้าหมายเป๊ะ', () => {
    assert.equal(valueAt(1249, 900, 900), 1249)
    assert.equal(valueAt(1249, 5000, 900), 1249)
  })
  it('เวลาศูนย์ได้ศูนย์', () => {
    assert.equal(valueAt(1249, 0, 900), 0)
    assert.equal(valueAt(1249, -10, 900), 0)
  })
  it('duration ไม่ถูกต้องให้ข้ามแอนิเมชัน', () => {
    assert.equal(valueAt(303, 10, 0), 303)
    assert.equal(valueAt(303, 10, -1), 303)
  })
  it('ค่าเป้าหมายไม่ใช่ตัวเลขก็คืนไปตรง ๆ ไม่พัง', () => {
    assert.equal(valueAt(NaN, 10, 900), NaN)
    assert.equal(valueAt(Infinity, 10, 900), Infinity)
  })
  it('คืนจำนวนเต็มเสมอ', () => {
    for (const e of [1, 50, 123, 400, 899]) {
      assert.equal(valueAt(1249, e, 900) % 1, 0, `elapsed=${e}`)
    }
  })
  it('ไม่เกินค่าเป้าหมายระหว่างทาง', () => {
    for (let e = 0; e <= 900; e += 25) {
      const v = valueAt(1249, e, 900)
      assert.ok(v >= 0 && v <= 1249, `elapsed=${e} ได้ ${v}`)
    }
  })
  it('ไต่ขึ้นตามเวลา', () => {
    let prev = -1
    for (let e = 0; e <= 900; e += 50) {
      const v = valueAt(303, e, 900)
      assert.ok(v >= prev, `ย้อนกลับที่ elapsed=${e}`)
      prev = v
    }
  })
  it('ค่าติดลบนับลงได้', () => {
    assert.equal(valueAt(-50, 900, 900), -50)
    assert.ok(valueAt(-50, 450, 900) <= 0)
  })
  it('ศูนย์ก็ยังเป็นศูนย์', () => {
    assert.equal(valueAt(0, 450, 900), 0)
  })
})
