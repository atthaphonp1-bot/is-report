// เทส github.js — รันด้วย `npm test` (node --test ของ Node 20 ไม่ต้องลง dependency เพิ่ม)
// fetchImpl/sleepImpl ถูกออกแบบให้ฉีดเข้ามาได้ จึงไม่ต้องยิง GitHub จริง
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { latestRun, triggerSync, waitForRun } from './github.js'

const ARGS = { owner: 'o', repo: 'r', workflow: 'sync.yml', token: 't' }

function fakeFetch(responses) {
  const calls = []
  const queue = [...responses]
  const impl = async (url, init) => {
    calls.push({ url, init })
    const next = queue.length > 1 ? queue.shift() : queue[0]
    return {
      ok: next.status >= 200 && next.status < 300,
      status: next.status,
      json: async () => next.body ?? {},
    }
  }
  impl.calls = calls
  return impl
}

const run = (over = {}) => ({
  id: 1, status: 'completed', conclusion: 'success',
  html_url: 'https://x', created_at: '2026-10-18T10:00:00Z', ...over,
})

describe('triggerSync', () => {
  it('204 ถือว่าสำเร็จ และส่ง header ครบ', async () => {
    const f = fakeFetch([{ status: 204 }])
    assert.deepEqual(await triggerSync({ ...ARGS, fetchImpl: f }), { ok: true })
    const { url, init } = f.calls[0]
    assert.ok(url.endsWith('/repos/o/r/actions/workflows/sync.yml/dispatches'))
    assert.equal(init.method, 'POST')
    assert.equal(init.headers.Authorization, 'Bearer t')
    assert.equal(init.headers['X-GitHub-Api-Version'], '2022-11-28')
    assert.deepEqual(JSON.parse(init.body), { ref: 'main' })
  })

  it('401 บอกว่า token ไม่ถูกต้อง (UpdateButton อาศัยข้อความนี้ลบ token ทิ้ง)', async () => {
    await assert.rejects(
      triggerSync({ ...ARGS, fetchImpl: fakeFetch([{ status: 401 }]) }),
      /token ไม่ถูกต้อง/,
    )
  })

  it('403 บอกเรื่องสิทธิ์ Actions', async () => {
    await assert.rejects(
      triggerSync({ ...ARGS, fetchImpl: fakeFetch([{ status: 403 }]) }),
      /Actions: Read and write/,
    )
  })

  it('404 บอกว่าหา workflow ไม่เจอ', async () => {
    await assert.rejects(
      triggerSync({ ...ARGS, fetchImpl: fakeFetch([{ status: 404 }]) }),
      /ไม่พบ workflow/,
    )
  })

  it('status อื่นบอกเลข HTTP', async () => {
    await assert.rejects(
      triggerSync({ ...ARGS, fetchImpl: fakeFetch([{ status: 500 }]) }),
      /HTTP 500/,
    )
  })

  it('ขาด token แล้วไม่ยิงเน็ตเลย', async () => {
    const f = fakeFetch([{ status: 204 }])
    await assert.rejects(triggerSync({ ...ARGS, token: '', fetchImpl: f }), /ขาดข้อมูล/)
    assert.equal(f.calls.length, 0)
  })
})

describe('latestRun', () => {
  it('ไม่มี run เลยคืน null', async () => {
    const f = fakeFetch([{ status: 200, body: { workflow_runs: [] } }])
    assert.equal(await latestRun({ ...ARGS, fetchImpl: f }), null)
  })

  it('ไม่มี token ก็อ่านได้ และไม่ส่ง Authorization', async () => {
    const f = fakeFetch([{ status: 200, body: { workflow_runs: [run()] } }])
    const out = await latestRun({ ...ARGS, token: '', fetchImpl: f })
    assert.equal(out.id, 1)
    assert.equal(f.calls[0].init.headers.Authorization, undefined)
  })

  it('after ที่ใหม่กว่า run -> ถือว่ายังไม่มี run ใหม่', async () => {
    const f = fakeFetch([{ status: 200, body: { workflow_runs: [run()] } }])
    const after = new Date('2026-10-18T11:00:00Z').getTime()
    assert.equal(await latestRun({ ...ARGS, fetchImpl: f, after }), null)
  })

  it('after ที่เก่ากว่า run -> คืน run ปกติ', async () => {
    const f = fakeFetch([{ status: 200, body: { workflow_runs: [run()] } }])
    const after = new Date('2026-10-18T09:00:00Z').getTime()
    assert.equal((await latestRun({ ...ARGS, fetchImpl: f, after })).id, 1)
  })

  it('status ไม่ ok แล้วโยน error', async () => {
    await assert.rejects(
      latestRun({ ...ARGS, fetchImpl: fakeFetch([{ status: 500 }]) }),
      /HTTP 500/,
    )
  })
})

describe('waitForRun', () => {
  it('รอจน completed แล้วคืน run', async () => {
    const f = fakeFetch([
      { status: 200, body: { workflow_runs: [run({ status: 'queued' })] } },
      { status: 200, body: { workflow_runs: [run({ status: 'in_progress' })] } },
      { status: 200, body: { workflow_runs: [run({ status: 'completed' })] } },
    ])
    const seen = []
    const out = await waitForRun({
      ...ARGS, fetchImpl: f, sleepImpl: async () => {},
      onProgress: (r) => seen.push(r?.status ?? null),
    })
    assert.equal(out.status, 'completed')
    assert.deepEqual(seen, ['queued', 'in_progress', 'completed'])
  })

  it('ไม่หลงคิดว่าเสร็จเพราะ run เก่าที่ completed ไปแล้ว', async () => {
    // นี่คือบั๊กที่ QA เจอ: หลัง dispatch GitHub ยังไม่สร้าง run ใหม่ runs[0] จึงเป็นรอบก่อน
    const old = run({ id: 1, created_at: '2026-10-18T09:00:00Z', status: 'completed' })
    const fresh = run({ id: 2, created_at: '2026-10-18T10:05:00Z', status: 'completed' })
    const f = fakeFetch([
      { status: 200, body: { workflow_runs: [old] } },
      { status: 200, body: { workflow_runs: [fresh] } },
    ])
    const out = await waitForRun({
      ...ARGS, fetchImpl: f, sleepImpl: async () => {},
      after: new Date('2026-10-18T10:00:00Z').getTime(),
    })
    assert.equal(out.id, 2, 'ต้องรอ run ใหม่ ไม่ใช่คืน run เก่า')
  })

  it('หมดเวลาแล้วโยน error ที่บอกทางออกให้ผู้ใช้', async () => {
    const f = fakeFetch([{ status: 200, body: { workflow_runs: [run({ status: 'queued' })] } }])
    await assert.rejects(
      waitForRun({ ...ARGS, fetchImpl: f, sleepImpl: async () => {}, timeoutMs: 0 }),
      /หน้า Actions/,
    )
  })
})
