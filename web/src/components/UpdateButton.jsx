// ปุ่ม "อัปเดตข้อมูล" — สั่ง GitHub Actions ให้ไป sync Google Drive แล้วรอจนเสร็จ
//
// ทำไมต้องมี token: หน้านี้เป็นไฟล์ static บน GitHub Pages ไม่มี backend ที่เก็บความลับได้
// การสั่ง workflow ต้องมีสิทธิ์ Actions: write จึงให้ผู้ดูแลกรอก fine-grained PAT ของตัวเอง
// ครั้งเดียว เก็บใน localStorage ของ browser ตัวเอง ไม่ฝังใน source (ถ้าฝังใน repo public
// GitHub จะ revoke ให้อัตโนมัติ) ครูทั่วไปไม่มี token ก็ยังดูรายงานได้ปกติ แค่กดปุ่มไม่ได้
import { useState } from 'react'

import { ACTIONS_URL, GITHUB_OWNER, GITHUB_REPO, SYNC_WORKFLOW } from '../config.js'
import { clearToken, getToken, setToken, triggerSync, waitForRun } from '../lib/github.js'

const ARGS = { owner: GITHUB_OWNER, repo: GITHUB_REPO, workflow: SYNC_WORKFLOW }

export default function UpdateButton({ onDone }) {
  const [state, setState] = useState('idle') // idle | asking | running | done | error
  const [message, setMessage] = useState('')
  const [tokenInput, setTokenInput] = useState('')

  async function run(token) {
    setState('running')
    setMessage('กำลังสั่งให้ GitHub ไปอ่าน Google Drive…')
    try {
      // จดเวลาไว้ "ก่อน" สั่ง แล้วส่งเป็น after ให้ waitForRun เพื่อไม่ให้ไปเห็น run เก่าที่จบ
      // ไปแล้วแล้วเข้าใจผิดว่าอัปเดตเสร็จ เผื่อนาฬิกาเครื่องเร็วกว่าของ GitHub ไว้ 60 วินาที
      const after = Date.now() - 60_000
      await triggerSync({ ...ARGS, token })
      await waitForRun({
        ...ARGS,
        token,
        after,
        onProgress: (run) =>
          setMessage(
            run === null
              ? 'กำลังรอให้ GitHub เริ่มทำงาน…'
              : `กำลังอัปเดต (สถานะ: ${run.status})…`,
          ),
      })
      setState('done')
      setMessage('อัปเดตเสร็จแล้ว กำลังโหลดข้อมูลใหม่')
      // Pages ใช้เวลา deploy อีกครู่หลัง run จบ รอสักหน่อยก่อนดึงไฟล์ใหม่
      setTimeout(() => onDone?.(), 4000)
    } catch (err) {
      // token ใช้ไม่ได้ -> ลบทิ้งทันที ไม่งั้นกดปุ่มซ้ำก็เจอ error เดิมวนไปจนกว่าจะเห็นปุ่ม "ลืม token"
      if (err.message.includes('token ไม่ถูกต้อง')) {
        clearToken()
        setState('asking')
        setMessage(err.message)
        return
      }
      setState('error')
      setMessage(err.message)
    }
  }

  function start() {
    const token = getToken()
    if (token) run(token)
    else setState('asking')
  }

  function submitToken(event) {
    event.preventDefault()
    if (!setToken(tokenInput)) {
      setMessage('เก็บ token ไม่ได้ — เบราว์เซอร์อาจปิดการเก็บข้อมูลของเว็บไว้')
      return
    }
    setTokenInput('')
    run(getToken())
  }

  function forget() {
    clearToken()
    setState('idle')
    setMessage('ลบ token ออกจากเครื่องนี้แล้ว')
  }

  if (state === 'asking') {
    return (
      <form onSubmit={submitToken} className="surface w-full space-y-2.5 p-4">
        <p className="text-xs leading-relaxed text-dim">
          ใส่ GitHub token ของผู้ดูแล (fine-grained PAT ที่ให้สิทธิ์เฉพาะ repo นี้ และเปิดเฉพาะ
          <span className="font-medium"> Actions: Read and write</span>) เก็บไว้ในเครื่องนี้เท่านั้น
        </p>
        <input
          type="password"
          value={tokenInput}
          onChange={(e) => setTokenInput(e.target.value)}
          placeholder="github_pat_…"
          autoComplete="off"
          className="field"
        />
        {message && <p className="text-xs text-warn">{message}</p>}
        <div className="flex gap-2">
          <button type="submit" className="btn-accent">
            บันทึกแล้วอัปเดตเลย
          </button>
          <button
            type="button"
            onClick={() => setState('idle')}
            className="pill"
          >
            ยกเลิก
          </button>
        </div>
      </form>
    )
  }

  return (
    <div className="flex min-w-0 flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={start}
        disabled={state === 'running'}
        className="btn-accent"
      >
        {state === 'running' ? 'กำลังอัปเดต…' : 'อัปเดตข้อมูล'}
      </button>
      {message && (
        <span className={`text-xs ${state === 'error' ? 'text-warn' : 'text-dim'}`}>
          {message}
        </span>
      )}
      {state === 'error' && (
        <>
          <a href={ACTIONS_URL} target="_blank" rel="noreferrer" className="text-xs text-accent underline">
            กดอัปเดตจากหน้า GitHub แทน
          </a>
          <button type="button" onClick={forget} className="text-xs text-faint underline">
            ลืม token
          </button>
        </>
      )}
    </div>
  )
}
