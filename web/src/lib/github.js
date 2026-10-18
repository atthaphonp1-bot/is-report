/**
 * Reads the admin's GitHub token from localStorage key "is_report_gh_token".
 * @returns {string|null} The token or null if not found or storage is unavailable
 */
export function getToken() {
  try {
    const token = localStorage.getItem("is_report_gh_token");
    return token?.trim() || null;
  } catch {
    return null;
  }
}

/**
 * Stores a GitHub token in localStorage.
 * @param {string} token - The token to store
 * @returns {boolean} True if stored successfully, false otherwise
 */
export function setToken(token) {
  try {
    const trimmed = token?.trim();
    if (!trimmed) return false;
    localStorage.setItem("is_report_gh_token", trimmed);
    return true;
  } catch {
    return false;
  }
}

/**
 * Removes the GitHub token from localStorage.
 */
export function clearToken() {
  try {
    localStorage.removeItem("is_report_gh_token");
  } catch {
    // Ignore errors
  }
}

/**
 * Triggers a GitHub Actions workflow dispatch.
 * @param {Object} params - Parameters
 * @param {string} params.owner - Repository owner
 * @param {string} params.repo - Repository name
 * @param {string} params.workflow - Workflow filename
 * @param {string} params.token - GitHub token
 * @param {string} [params.ref="main"] - Git ref to run
 * @param {Function} [params.fetchImpl=fetch] - Fetch implementation
 * @returns {Promise<{ok: boolean}>} Resolves when successful
 * @throws {Error} With specific messages for different failure cases
 */
export async function triggerSync({ owner, repo, workflow, token, ref = "main", fetchImpl = fetch }) {
  if (!owner || !repo || !workflow || !token) {
    throw new Error("ขาดข้อมูล — ต้องระบุ owner, repo, workflow และ token");
  }

  const url = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflow}/dispatches`;
  const response = await fetchImpl(url, {
    method: "POST",
    headers: {
      "Accept": "application/vnd.github+json",
      "Authorization": `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ ref })
  });

  if (response.ok) {
    return { ok: true };
  }

  if (response.status === 401) {
    throw new Error("token ไม่ถูกต้องหรือหมดอายุ — กรอกใหม่อีกครั้ง");
  }

  if (response.status === 403) {
    throw new Error("token นี้ไม่มีสิทธิ์ Actions: Read and write ของ repo นี้");
  }

  if (response.status === 404) {
    throw new Error("ไม่พบ workflow หรือ repo — ตรวจชื่อ owner/repo/workflow อีกครั้ง");
  }

  throw new Error(`สั่ง sync ไม่สำเร็จ (HTTP ${response.status})`);
}

/**
 * Gets the latest workflow run.
 * @param {Object} params - Parameters
 * @param {string} params.owner - Repository owner
 * @param {string} params.repo - Repository name
 * @param {string} params.workflow - Workflow filename
 * @param {string} [params.token] - GitHub token (optional for public repos)
 * @param {Function} [params.fetchImpl=fetch] - Fetch implementation
 * @returns {Promise<Object|null>} The run object or null if none found
 * @throws {Error} When the request fails
 */
export async function latestRun({ owner, repo, workflow, token, fetchImpl = fetch, after = 0 }) {
  const url = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflow}/runs?per_page=1`;
  const headers = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetchImpl(url, { headers });

  if (!response.ok) {
    throw new Error(`อ่านสถานะ run ไม่ได้ (HTTP ${response.status})`);
  }

  const data = await response.json();
  const runs = data?.workflow_runs;

  if (!runs || runs.length === 0) {
    return null;
  }

  const run = runs[0];

  // ข้าม run เก่า: หลังสั่ง dispatch (ตอบ 204) GitHub ใช้เวลาสักครู่กว่า run ใหม่จะโผล่ใน API
  // ระหว่างนั้น runs[0] ยังเป็นรอบ cron ก่อนหน้าที่ completed ไปแล้ว ถ้าไม่กรองออก waitForRun
  // จะเห็น "completed" ตั้งแต่รอบแรกแล้วบอกผู้ใช้ว่าอัปเดตเสร็จทั้งที่ยังไม่เริ่มด้วยซ้ำ
  if (after && new Date(run.created_at).getTime() < after) {
    return null;
  }

  return {
    id: run.id,
    status: run.status,
    conclusion: run.conclusion,
    htmlUrl: run.html_url,
    createdAt: run.created_at
  };
}

/**
 * Polls for a completed workflow run.
 * @param {Object} params - Parameters
 * @param {string} params.owner - Repository owner
 * @param {string} params.repo - Repository name
 * @param {string} params.workflow - Workflow filename
 * @param {string} [params.token] - GitHub token
 * @param {Function} [params.fetchImpl=fetch] - Fetch implementation
 * @param {Function} [params.sleepImpl] - Sleep implementation
 * @param {number} [params.intervalMs=5000] - Polling interval
 * @param {number} [params.timeoutMs=300000] - Timeout in milliseconds
 * @param {Function} [params.onProgress] - Progress callback
 * @returns {Promise<Object>} The completed run object
 * @throws {Error} When timeout occurs or request fails
 */
export async function waitForRun({
  owner,
  repo,
  workflow,
  token,
  fetchImpl = fetch,
  sleepImpl,
  intervalMs = 5000,
  timeoutMs = 300000,
  onProgress,
  after = 0
}) {
  const startTime = Date.now();
  const sleep = sleepImpl || ((ms) => new Promise(resolve => setTimeout(resolve, ms)));

  while (Date.now() - startTime < timeoutMs) {
    const run = await latestRun({ owner, repo, workflow, token, fetchImpl, after });

    if (typeof onProgress === "function") {
      onProgress(run);
    }

    if (run?.status === "completed") {
      return run;
    }

    await sleep(intervalMs);
  }

  throw new Error("รอผลนานเกินไป — ไปดูสถานะที่หน้า Actions ของ GitHub ได้เลย");
}