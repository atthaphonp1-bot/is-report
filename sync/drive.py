"""อ่าน Google Drive ด้วย service account แล้ว mirror ลงดิสก์ — พอร์ตจาก
backend/app/gdrive/sync.py ของ repo เดิม (Agentic_IS) ตัดส่วนที่ผูกกับ sqlite/ingest ออก

ต่างจากของเดิม: ที่นี่ไม่มีฐานข้อมูล ไม่มี checkpoint ไม่มี incremental sync — workflow รัน
ในเครื่องใหม่ทุกรอบ จึงดาวน์โหลดทั้งโฟลเดอร์ใหม่หมดทุกครั้ง (ไฟล์ไม่กี่สิบตัว ใช้เวลาไม่กี่วินาที)
scope ยังเป็น drive.readonly เท่านั้นเหมือนเดิม — ห้ามขอ scope เขียนเด็ดขาด
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


logger = logging.getLogger(__name__)

# --- Google Workspace mimeType -> export format ---------------------------
# ตาม docs/PLAN.md §6/§8: export เฉพาะ Google Docs/Sheets เป็น docx/xlsx เท่านั้น (ไฟล์
# mimeType อื่นที่ไม่ใช่ Google Workspace format ให้ download_binary ตรง ๆ)
GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
GOOGLE_SHEET_MIME = "application/vnd.google-apps.spreadsheet"
GOOGLE_FOLDER_MIME = "application/vnd.google-apps.folder"

GOOGLE_EXPORT_MIME_MAP: dict[str, tuple[str, str]] = {
    GOOGLE_DOC_MIME: (
        "docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    GOOGLE_SHEET_MIME: (
        "xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
}

DRIVE_READONLY_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
_LIST_FIELDS = "nextPageToken, files(id,name,mimeType,modifiedTime,trashed,parents)"

# path separator + NUL + ตัวควบคุมอื่น ๆ ที่อันตรายถ้าปนไปกับชื่อไฟล์/โฟลเดอร์บนดิสก์
_UNSAFE_PATH_CHARS = re.compile(r"[\\/\x00-\x1f]")


class GDriveConfigError(RuntimeError):
    """ตั้งค่า Google Drive sync ไม่ครบ (folder id ว่าง / ไม่มีไฟล์ credential)

    ตั้งใจแยก exception type นี้ออกจาก error อื่น ๆ ระหว่าง sync (network, ไฟล์เดียวพัง ฯลฯ)
    เพื่อให้ผู้เรียก (admin endpoint, CLI) แยกแยะได้ว่าเป็นปัญหา "ยังตั้งค่าไม่ครบ" ที่ต้องแก้ .env
    ก่อน ไม่ใช่ปัญหาระหว่างรัน sync ปกติ — ดูวิธีตั้งค่าใน docs/RUNBOOK.md
    """


class DriveClientProtocol(Protocol):
    """Interface ที่ sync_once ต้องการจริง ๆ — FakeDriveClient ในเทส implement อันนี้แทนของจริงได้"""

    def list_children(self, folder_id: str) -> list[dict[str, Any]]: ...

    def download_binary(self, file_id: str) -> bytes: ...

    def export_google_doc(self, file_id: str, target_mime: str) -> bytes: ...


class DriveClient:
    """Thin wrapper รอบ googleapiclient.discovery — สร้างได้เฉพาะตอนมี credential จริงเท่านั้น

    Auth ด้วย Service Account scope `drive.readonly` เท่านั้น (ดู docs/PLAN.md §6) — ห้ามขอ
    scope เขียน (`drive` หรือ `drive.file`) เด็ดขาด เพราะ service account ไม่มี storage quota
    ของตัวเอง เขียนกลับ Drive จะอัปโหลดไม่ผ่าน
    """

    def __init__(self, sa_json_path: str) -> None:
        # import แบบ lazy (ไม่ใช่ top-level ของไฟล์) เพื่อให้ sync_once() ที่ inject fake client
        # ในเทสไม่ต้องพึ่ง googleapiclient/google-auth ติดตั้งครบหรือมี credential ไฟล์จริงเลย
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        # รับ path มาจากผู้เรียก ไม่อ่าน settings เอง — ใน GitHub Actions ไฟล์นี้ถูกเขียนจาก
        # secret GDRIVE_SA_JSON ลง temp file ชั่วคราว (ดู export_report.py)
        sa_path = Path(sa_json_path).expanduser()
        credentials = Credentials.from_service_account_file(
            str(sa_path), scopes=DRIVE_READONLY_SCOPES
        )
        self._service = build("drive", "v3", credentials=credentials, cache_discovery=False)

    def list_children(self, folder_id: str) -> list[dict[str, Any]]:
        """คืนไฟล์/โฟลเดอร์ลูกโดยตรงทั้งหมดของ folder_id (วน pageToken ให้ครบ)

        ไม่ query `trashed=false` ตรง ๆ เพราะ Drive API v3 ไม่คืนไฟล์ trashed มาโดย default
        อยู่แล้ว (ไฟล์ trashed/ลบถาวร/ย้ายออกจากโฟลเดอร์ หายไปจาก listing เฉย ๆ เหมือนกันหมด) —
        การตรวจจับไฟล์ที่หายไปทำผ่าน reconcile ด้วย drive_file_id ใน sync_once() แทน ไม่พึ่ง
        field `trashed` เป็นกลไกหลัก (ดู docstring บนสุดของไฟล์นี้)
        """
        results: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            response = (
                self._service.files()
                .list(
                    q=f"'{folder_id}' in parents",
                    fields=_LIST_FIELDS,
                    pageSize=1000,
                    pageToken=page_token,
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                )
                .execute()
            )
            results.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return results

    def download_binary(self, file_id: str) -> bytes:
        return self._service.files().get_media(fileId=file_id).execute()

    def export_google_doc(self, file_id: str, target_mime: str) -> bytes:
        return self._service.files().export_media(fileId=file_id, mimeType=target_mime).execute()



def _utcnow_iso() -> str:
    """ISO8601 UTC พร้อม millisecond + 'Z' — เก็บเป็น checkpoint ในตาราง gdrive_sync_state
    (เทียบกับ modifiedTime ตอนใช้งานจริงผ่าน `_parse_drive_time`, ไม่ใช่ string compare ตรง ๆ)"""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_drive_time(value: str) -> datetime:
    """Parse RFC3339 timestamp (Google Drive `modifiedTime` หรือ checkpoint ของเราเอง) เป็น
    datetime tz-aware แล้วเทียบตามเวลาจริง — เดิมเทียบ string `>` ตรง ๆ ซึ่งเสี่ยงผิดถ้ารูปแบบ
    เศษวินาทีไม่ตรงกันเป๊ะ (เช่น Drive คืน '...:00Z' ไม่มีเศษวินาที ปนกับ checkpoint ของเราที่มี
    '.000Z' เสมอ — '.' < 'Z' ใน ASCII ทำให้เรียงลำดับผิดได้) parse เป็น datetime ตัดปัญหานี้ทิ้งทั้งกลุ่ม
    """
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _sanitize_segment(name: str, fallback_id: str) -> str:
    """ทำความสะอาด 1 ชื่อ (ไฟล์หรือโฟลเดอร์) จาก Drive ก่อนเอาไปต่อเป็น path บนดิสก์

    Google Drive อนุญาตให้ชื่อไฟล์/โฟลเดอร์มีอักขระ '/', '\\\\', หรือเป็น '..'/'.' ล้วน ๆ ได้
    (ต่างจาก filesystem ปกติที่ตีความเป็น path separator/parent-dir reference) ถ้าไม่ sanitize
    ก่อน คนอัปโหลดไฟล์ชื่อ '../../etc/passwd' ขึ้น Drive จะทำให้ sync เขียนไฟล์หลุดออกนอก
    files_dir ได้จริง (path traversal — พิสูจน์แล้วจาก QA review) แทนอักขระอันตรายด้วย '_' แล้ว
    ถ้าผลลัพธ์ว่างเปล่าหรือเป็น '.'/'..' ล้วน ๆ (parent/current-dir reference) ใช้ drive file id
    แทนทั้งชื่อ (กันชื่อไฟล์ที่ sanitize แล้วกลายเป็นค่าว่าง/อันตรายอยู่ดี)
    """
    cleaned = _UNSAFE_PATH_CHARS.sub("_", name).strip()
    cleaned = cleaned.strip(".")  # เหลือ "" ถ้า input เป็น '.'/'..'/'...' ล้วน ๆ
    if not cleaned:
        return f"_{fallback_id}"
    return cleaned


def _local_filename(item: dict[str, Any]) -> str:
    """ชื่อไฟล์ local ที่จะ mirror ไป — Google Docs/Sheets มักไม่มีนามสกุลไฟล์ใน `name` เลย
    (เช่น "ประกาศประชุม" เฉย ๆ) ต้องเติม .docx/.xlsx เองตาม export format เพื่อให้
    ingest/loaders.py (dispatch ตามนามสกุล) และ pipeline._infer_category (ตีความจาก subfolder
    ไม่ใช่นามสกุล) ทำงานถูกต้อง — sanitize ชื่อก่อนเสมอ (ดู `_sanitize_segment`)"""
    mime = item.get("mimeType", "")
    export = GOOGLE_EXPORT_MIME_MAP.get(mime)
    name = _sanitize_segment(str(item["name"]), fallback_id=str(item["id"]))
    if export is not None:
        ext = "." + export[0]
        if not name.lower().endswith(ext):
            name = f"{name}{ext}"
    return name


def _walk_drive_tree(
    client: DriveClientProtocol, folder_id: str, prefix: Path = Path()
) -> list[tuple[Path, dict[str, Any]]]:
    """เดินโฟลเดอร์ Drive แบบ recursive คืน [(relative_path, item), ...] ของ "ไฟล์" ทั้งหมด
    (ไม่รวม item ที่เป็นโฟลเดอร์เอง) subfolder ชั้นแรก = category ตาม §6 — ไม่ต้องทำ category
    logic ซ้ำที่นี่ เพราะแค่ mirror โครงสร้างไป files_dir แล้ว pipeline._infer_category จะอ่านเอง

    ไม่รวมไฟล์/ไม่ recurse เข้าโฟลเดอร์ที่ `trashed=true` (เผื่อ Drive API คืน field นี้มาจริง ๆ
    ในบาง edge case — เป็น defense in depth เท่านั้น กลไกหลักในการตรวจจับไฟล์ที่ถูกลบคือ
    reconcile ด้วย drive_file_id ใน sync_once() ไม่ใช่พึ่ง field นี้ ดู docstring บนสุดของไฟล์)
    """
    out: list[tuple[Path, dict[str, Any]]] = []
    for item in client.list_children(folder_id):
        if item.get("trashed"):
            continue
        if item.get("mimeType") == GOOGLE_FOLDER_MIME:
            safe_name = _sanitize_segment(str(item["name"]), fallback_id=str(item["id"]))
            out.extend(_walk_drive_tree(client, item["id"], prefix / safe_name))
        else:
            out.append((prefix / _local_filename(item), item))
    return out


def _dedupe_rel_paths(
    entries: list[tuple[Path, dict[str, Any]]]
) -> tuple[list[tuple[Path, dict[str, Any]]], list[str]]:
    """Google Drive อนุญาตให้ 2 ไฟล์ (id ต่างกัน) ชื่อเดียวกันอยู่ในโฟลเดอร์เดียวกันได้ (ต่างจาก
    filesystem ปกติ) ถ้าไม่จัดการ ไฟล์ที่ mirror ไป local path เดียวกันจะทับกันเงียบ ๆ (silent
    data loss — พิสูจน์แล้วจาก QA review) เจอ collision ให้เติม `__<6 ตัวท้ายของ id>` ก่อนนามสกุล
    ของไฟล์ที่ชน (ตัวแรกที่เจอไม่ต้องแก้ชื่อ) แล้วบันทึกเป็น warning ให้ admin เห็นใน sync log
    """
    seen: dict[Path, str] = {}
    warnings: list[str] = []
    result: list[tuple[Path, dict[str, Any]]] = []

    for rel_path, item in entries:
        if rel_path in seen:
            file_id = str(item["id"])
            suffix = file_id[-6:]
            new_rel_path = rel_path.with_stem(f"{rel_path.stem}__{suffix}")
            warnings.append(
                f"ชื่อไฟล์ซ้ำใน Drive: '{rel_path}' (id={file_id}) ชนกับไฟล์ที่ id={seen[rel_path]} "
                f"— เปลี่ยนชื่อ local เป็น '{new_rel_path}' แทนเพื่อกันข้อมูลหาย"
            )
            rel_path = new_rel_path
        seen[rel_path] = str(item["id"])
        result.append((rel_path, item))

    return result, warnings


def _download_item(client: DriveClientProtocol, item: dict[str, Any]) -> bytes:
    mime = item.get("mimeType", "")
    export = GOOGLE_EXPORT_MIME_MAP.get(mime)
    if export is not None:
        _, target_mime = export
        return client.export_google_doc(item["id"], target_mime)
    return client.download_binary(item["id"])


def _drive_view_url(file_id: str) -> str:
    return f"https://drive.google.com/file/d/{file_id}/view"


def mirror_folder(
    client: DriveClientProtocol, folder_id: str, dest: Path
) -> tuple[list[Path], list[str]]:
    """ดาวน์โหลดทุกไฟล์ใต้ folder_id ลง dest โดยคงโครงสร้างโฟลเดอร์ คืน (ไฟล์ที่เขียน, warnings)

    ต่างจาก sync_once() เดิมที่ทำ incremental ด้วย checkpoint ในฐานข้อมูล — ที่นี่ดาวน์โหลดใหม่
    ทั้งหมดทุกรอบ เพราะ runner ของ GitHub Actions เป็นเครื่องเปล่าทุกครั้ง ไม่มีของเก่าให้เทียบ
    """
    entries, warnings = _dedupe_rel_paths(_walk_drive_tree(client, folder_id))
    written: list[Path] = []
    for rel_path, item in entries:
        target = dest / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_bytes(_download_item(client, item))
        except Exception as exc:  # ไฟล์เดียวพังไม่ควรทำให้ทั้งรอบล่ม — รายงานเป็น warning
            warnings.append(
                f"ดาวน์โหลดไม่สำเร็จ: '{rel_path}' (id={item.get('id')}) "
                f"{exc.__class__.__name__}: {exc}"
            )
            continue
        written.append(target)
    return written, warnings


__all__ = [
    "DriveClient",
    "DriveClientProtocol",
    "GDriveConfigError",
    "mirror_folder",
]
