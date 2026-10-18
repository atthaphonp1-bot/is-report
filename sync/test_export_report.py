"""เทส export_report — เน้นกรณีที่ "ไม่ควรเขียนทับข้อมูลเดิม" เพราะหน้าเว็บจะโล่งทันที"""
import json

import pytest

from sync import export_report, parse_is


@pytest.fixture
def roster(monkeypatch):
    """ให้ build_roster คืน roster ปลอม — ไม่ต้องมีไฟล์ .docx จริงในเทส"""
    rows = [{
        "room": "ม.1/1", "grade": "ม.1", "plan": "", "course_code": "ว1",
        "subject": "ก", "teacher": "ครูเอ",
        "projects": [{"name": "โครงงาน ก", "members": ["เด็กชายสมชาย"], "advisor": "ครูเอ"}],
    }]
    monkeypatch.setattr(parse_is, "build_roster", lambda files_dir: rows)
    return rows


def test_เขียนไฟล์แล้วคืนค่าสรุป(tmp_path, roster):
    out = tmp_path / "data" / "report.json"
    report = export_report.export(out, files_dir=tmp_path)
    assert out.exists()
    assert report["summary"]["rooms"] == 1
    assert report["summary"]["submitted"] == 1


def test_ไฟล์ที่เขียนมีรายชื่อสมาชิกครบ(tmp_path, roster):
    out = tmp_path / "report.json"
    export_report.export(out, files_dir=tmp_path)
    raw = out.read_text(encoding="utf-8")
    assert "เด็กชายสมชาย" in raw
    assert json.loads(raw)["includes_members"] is True


def test_ภาษาไทยไม่ถูก_escape(tmp_path, roster):
    """ensure_ascii=False เพื่อให้ diff ของ commit อ่านออก"""
    out = tmp_path / "report.json"
    export_report.export(out, files_dir=tmp_path)
    assert "ม.1/1" in out.read_text(encoding="utf-8")


def test_main_คืน_0_เมื่อสำเร็จ(tmp_path, roster):
    out = tmp_path / "report.json"
    assert export_report.main(["--out", str(out), "--files-dir", str(tmp_path)]) == 0


def test_main_คืน_2_และไม่แตะไฟล์เดิมเมื่อไม่พบไฟล์บัญชีจัดครู(tmp_path, monkeypatch):
    out = tmp_path / "report.json"
    out.write_text('{"ของเดิม": true}', encoding="utf-8")

    def ระเบิด(files_dir):
        raise parse_is.RosterNotFoundError("ยังไม่มีไฟล์บัญชีจัดครูเข้าสอน")

    monkeypatch.setattr(parse_is, "build_roster", ระเบิด)
    assert export_report.main(["--out", str(out), "--files-dir", str(tmp_path)]) == 2
    assert json.loads(out.read_text(encoding="utf-8")) == {"ของเดิม": True}


def test_main_คืน_1_เมื่อ_parse_ได้ศูนย์ห้อง(tmp_path, monkeypatch):
    """ศูนย์ห้องคือสัญญาณว่า parser หรือสิทธิ์ Drive มีปัญหา ไม่ใช่สภาพปกติ"""
    monkeypatch.setattr(parse_is, "build_roster", lambda files_dir: [])
    out = tmp_path / "report.json"
    assert export_report.main(["--out", str(out), "--files-dir", str(tmp_path)]) == 1


def test_ไม่มี_env_แล้วต้องฟ้อง(tmp_path, monkeypatch):
    monkeypatch.delenv("GDRIVE_FOLDER_ID", raising=False)
    monkeypatch.delenv("GDRIVE_SA_JSON", raising=False)
    with pytest.raises(export_report.ConfigError, match="GDRIVE_FOLDER_ID"):
        export_report.export(tmp_path / "report.json")


def test_env_ว่างถือว่าไม่ได้ตั้ง(tmp_path, monkeypatch):
    monkeypatch.setenv("GDRIVE_FOLDER_ID", "   ")
    with pytest.raises(export_report.ConfigError):
        export_report.export(tmp_path / "report.json")


def test_main_คืน_1_เมื่อ_config_ไม่ครบ(tmp_path, monkeypatch):
    monkeypatch.delenv("GDRIVE_FOLDER_ID", raising=False)
    assert export_report.main(["--out", str(tmp_path / "report.json")]) == 1


# --- กัน commit งอกทุกรอบ cron (QA 2026-10-18) ---------------------------------
def test_ข้อมูลไม่เปลี่ยนแล้วไฟล์ต้องไม่เปลี่ยน(tmp_path, roster):
    """cron ทุก 30 นาทีต้องไม่สร้าง commit ใหม่ถ้าครูไม่ได้ส่งงานเพิ่ม"""
    out = tmp_path / "report.json"
    export_report.export(out, files_dir=tmp_path)
    first = out.read_text(encoding="utf-8")
    export_report.export(out, files_dir=tmp_path)
    assert out.read_text(encoding="utf-8") == first


def test_ข้อมูลเปลี่ยนแล้วเวลาต้องขยับ(tmp_path, roster, monkeypatch):
    # ตรึงนาฬิกาเอง: ของจริงละเอียดระดับวินาที สองรอบในเทสจึงได้เวลาเท่ากันแล้วเทสวูบวาบ
    clock = iter(["2026-10-18T09:00:00Z", "2026-10-18T10:00:00Z"])
    monkeypatch.setattr(export_report, "_utcnow_iso", lambda: next(clock))

    out = tmp_path / "report.json"
    export_report.export(out, files_dir=tmp_path)
    before = json.loads(out.read_text(encoding="utf-8"))

    rows = roster + [{
        "room": "ม.2/1", "grade": "ม.2", "plan": "", "course_code": "", "subject": "",
        "teacher": "ครูบี", "projects": [],
    }]
    monkeypatch.setattr(parse_is, "build_roster", lambda files_dir: rows)
    export_report.export(out, files_dir=tmp_path)
    after = json.loads(out.read_text(encoding="utf-8"))

    assert after["summary"]["rooms"] == before["summary"]["rooms"] + 1
    assert after["summary"]["last_synced_at"] != before["summary"]["last_synced_at"]


def test_ไฟล์เดิมพังไม่ทำให้ล้ม(tmp_path, roster):
    out = tmp_path / "report.json"
    out.write_text("{ ไม่ใช่ json", encoding="utf-8")
    report = export_report.export(out, files_dir=tmp_path)
    assert report["summary"]["rooms"] == 1
