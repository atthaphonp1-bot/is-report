"""entry point ที่ GitHub Actions เรียก: Google Drive -> report.json

    python -m sync.export_report --out web/public/data/report.json

อ่าน config จาก environment variable (ไม่มี .env บน runner):
    GDRIVE_SA_JSON    เนื้อไฟล์ service account ทั้งก้อน (มาจาก repo secret)
    GDRIVE_FOLDER_ID  id ของโฟลเดอร์ Drive ที่ครูส่งงานเข้ามา

ไม่เขียนทับไฟล์เดิมถ้ายังหาไฟล์บัญชีจัดครูเข้าสอนไม่เจอ (RosterNotFoundError) — ไฟล์อาจหาย
ชั่วคราวจากสิทธิ์ Drive หรือครูเผลอย้ายโฟลเดอร์ ถ้าเขียนทับด้วยข้อมูลว่างหน้าเว็บจะโล่งทันที
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sync import drive, parse_is  # noqa: E402
from sync.report_shape import roster_to_report  # noqa: E402

logger = logging.getLogger("export_report")


class ConfigError(RuntimeError):
    """environment variable ที่จำเป็นหายไป — workflow ควร fail ให้เห็นชัด ๆ ไม่ใช่เขียน JSON ว่าง"""



def _keep_timestamp_if_unchanged(report: dict, out_path: Path) -> dict:
    """ถ้าข้อมูลเหมือนเดิมทุกอย่างยกเว้นเวลา ให้คงเวลาเดิมไว้ -> ไฟล์ไม่เปลี่ยน -> ไม่เกิด commit

    ไม่งั้น cron ทุก 30 นาทีจะสร้าง commit ใหม่ทุกครั้งเพราะ last_synced_at ขยับเสมอ
    (ราว 22 commit/วัน ทั้งที่ครูไม่ได้ส่งงานเพิ่มเลย) ความหมายของ last_synced_at จึงเป็น
    "ข้อมูลเปลี่ยนล่าสุดเมื่อไหร่" ไม่ใช่ "ตรวจล่าสุดเมื่อไหร่" ซึ่งตรงกับที่หน้าเว็บแสดงอยู่แล้ว
    """
    if not out_path.exists():
        return report
    try:
        previous = json.loads(out_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return report  # ไฟล์เดิมอ่านไม่ได้ -> เขียนทับด้วยของใหม่ไปเลย

    def without_time(d: dict) -> dict:
        copy = json.loads(json.dumps(d))
        copy.get("summary", {}).pop("last_synced_at", None)
        return copy

    if without_time(previous) == without_time(report):
        report["summary"]["last_synced_at"] = previous.get("summary", {}).get("last_synced_at")
    return report


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_env(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise ConfigError(
            f"ยังไม่ได้ตั้ง environment variable {name} — "
            f"ตั้งเป็น repo secret แล้วส่งเข้า step ผ่าน env: ใน .github/workflows/sync.yml"
        )
    return value


#: ไฟล์ตั้งต้นที่ commit ไว้ใน repo แล้ว copy ลงไปรวมกับไฟล์ที่โหลดจาก Drive ก่อน parse
#: มีไว้เพราะ "บัญชีจัดครูเข้าสอน" (รายชื่อครู_รายวิชา_IS_*.xlsx) ซึ่งเป็นแกนของรายงานทั้งหมด
#: ไม่ได้อยู่ในโฟลเดอร์ Drive ที่ครูส่งงานเข้ามา — ถ้าวันหนึ่งอัปโหลดเข้า Drive แล้ว ไฟล์จาก
#: Drive จะทับไฟล์ในนี้ให้เอง (copy ของ repo ก่อน แล้วค่อยโหลดจาก Drive ลงทับ)
INPUTS_DIR = Path(__file__).resolve().parent / "inputs"


def _copy_inputs(src: Path, dest: Path) -> list[str]:
    """copy ไฟล์ตั้งต้นจาก repo -> dest คืนชื่อไฟล์ที่ copy มา"""
    if not src.is_dir():
        return []
    copied = []
    for item in sorted(src.iterdir()):
        if item.is_file() and not item.name.startswith("."):
            shutil.copy2(item, dest / item.name)
            copied.append(item.name)
    return copied


def export(out_path: Path, *, files_dir: Path | None = None) -> dict:
    """ดึงข้อมูลจาก Drive แล้วเขียน out_path คืน report dict ที่เขียนลงไป

    `files_dir` ใส่เพื่อข้ามขั้นดาวน์โหลด (ใช้ตอนเทส / ตอนมีไฟล์อยู่ในเครื่องแล้ว)
    """
    with tempfile.TemporaryDirectory(prefix="is-report-") as tmp:
        tmp_dir = Path(tmp)
        warnings: list[str] = []

        if files_dir is None:
            folder_id = _require_env("GDRIVE_FOLDER_ID")
            # เขียน credential ลงไฟล์ชั่วคราวใน temp dir ที่ลบทิ้งแน่นอนเมื่อจบ — google-auth
            # รับได้แค่ path ไม่รับ string ส่วน secret บน runner มาเป็น env เท่านั้น
            sa_path = tmp_dir / "sa.json"
            sa_path.write_text(_require_env("GDRIVE_SA_JSON"), encoding="utf-8")
            sa_path.chmod(0o600)

            files_dir = tmp_dir / "files"
            files_dir.mkdir()
            copied = _copy_inputs(INPUTS_DIR, files_dir)
            if copied:
                logger.info("ใช้ไฟล์ตั้งต้นจาก repo %d ไฟล์: %s", len(copied), ", ".join(copied))

            client = drive.DriveClient(str(sa_path))
            written, warnings = drive.mirror_folder(client, folder_id, files_dir)
            logger.info("ดาวน์โหลดจาก Drive %d ไฟล์", len(written))

        for w in warnings:
            logger.warning("%s", w)

        roster = parse_is.build_roster(files_dir)

    report = roster_to_report(roster, last_synced_at=_utcnow_iso())
    report = _keep_timestamp_if_unchanged(report, out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # ensure_ascii=False ให้ภาษาไทยอ่านออกใน diff ของ commit, sort_keys ให้ diff นิ่ง
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Google Drive -> report.json")
    parser.add_argument("--out", required=True, type=Path, help="ที่เขียน report.json")
    parser.add_argument("--files-dir", type=Path, default=None, help="ข้ามการดาวน์โหลด ใช้ไฟล์ในเครื่อง")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        report = export(args.out, files_dir=args.files_dir)
    except parse_is.RosterNotFoundError as exc:
        # ไม่ใช่ error ของระบบ แต่ไม่ควรเขียนทับข้อมูลเดิมด้วยของว่าง -> exit code 2 ให้ workflow
        # ข้ามขั้น commit ไปเฉย ๆ (ดู sync.yml) โดยไม่ขึ้นเป็น run สีแดง
        logger.warning("ข้ามรอบนี้: %s", exc)
        return 2
    except (ConfigError, drive.GDriveConfigError) as exc:
        logger.error("%s", exc)
        return 1

    s = report["summary"]
    logger.info(
        "เขียน %s แล้ว: %d ห้อง, ส่งแล้ว %d ห้อง, %d โครงงาน, นักเรียน %d คน",
        args.out, s["rooms"], s["submitted"], s["projects"], s["students"],
    )
    if s["rooms"] == 0:
        logger.error("ไม่พบห้องเลยแม้แต่ห้องเดียว — น่าจะผิดปกติ ไม่ commit รอบนี้")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
