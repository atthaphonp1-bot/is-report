"""เทส mirror_folder — ไม่ยิง Google จริง ใช้ fake client ฉีดเข้าไปตาม DriveClientProtocol"""
import pytest

from sync import drive

DOC = "application/vnd.google-apps.document"
FOLDER = "application/vnd.google-apps.folder"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class FakeDrive:
    """children: {folder_id: [item, ...]} — item ใช้คีย์เดียวกับที่ Drive API v3 คืนมา"""

    def __init__(self, children, fail_ids=()):
        self.children = children
        self.fail_ids = set(fail_ids)
        self.exported = []
        self.downloaded = []

    def list_children(self, folder_id):
        return list(self.children.get(folder_id, []))

    def download_binary(self, file_id):
        if file_id in self.fail_ids:
            raise RuntimeError("drive ล่ม")
        self.downloaded.append(file_id)
        return f"bin:{file_id}".encode()

    def export_google_doc(self, file_id, target_mime):
        if file_id in self.fail_ids:
            raise RuntimeError("drive ล่ม")
        self.exported.append((file_id, target_mime))
        return f"export:{file_id}".encode()


def item(file_id, name, mime="application/pdf", **extra):
    return {"id": file_id, "name": name, "mimeType": mime, "modifiedTime": "2026-10-18T00:00:00Z", **extra}


def test_ดาวน์โหลดไฟล์ชั้นเดียว(tmp_path):
    client = FakeDrive({"root": [item("f1", "ก.pdf")]})
    written, warnings = drive.mirror_folder(client, "root", tmp_path)
    assert warnings == []
    assert [p.name for p in written] == ["ก.pdf"]
    assert (tmp_path / "ก.pdf").read_bytes() == b"bin:f1"


def test_คงโครงสร้างโฟลเดอร์ย่อย(tmp_path):
    client = FakeDrive({
        "root": [item("d1", "โครงงาน", FOLDER)],
        "d1": [item("f1", "ก.pdf")],
    })
    written, _ = drive.mirror_folder(client, "root", tmp_path)
    assert written == [tmp_path / "โครงงาน" / "ก.pdf"]
    assert (tmp_path / "โครงงาน" / "ก.pdf").exists()


def test_google_doc_ถูก_export_เป็น_docx(tmp_path):
    client = FakeDrive({"root": [item("g1", "บัญชีจัดครู", DOC)]})
    written, _ = drive.mirror_folder(client, "root", tmp_path)
    assert client.exported == [("g1", DOCX)]
    assert client.downloaded == []
    assert written[0].suffix == ".docx"


def test_ข้ามไฟล์ที่อยู่ในถังขยะ(tmp_path):
    client = FakeDrive({"root": [item("f1", "ก.pdf", trashed=True), item("f2", "ข.pdf")]})
    written, _ = drive.mirror_folder(client, "root", tmp_path)
    assert [p.name for p in written] == ["ข.pdf"]


def test_ข้ามโฟลเดอร์ที่อยู่ในถังขยะ(tmp_path):
    client = FakeDrive({
        "root": [item("d1", "เก่า", FOLDER, trashed=True)],
        "d1": [item("f1", "ก.pdf")],
    })
    written, _ = drive.mirror_folder(client, "root", tmp_path)
    assert written == []


def test_ชื่อไฟล์ซ้ำไม่ทับกันและมี_warning(tmp_path):
    """Drive ยอมให้ 2 ไฟล์ชื่อเดียวกันในโฟลเดอร์เดียวกัน — ถ้าทับกันคือข้อมูลหายเงียบ ๆ"""
    client = FakeDrive({"root": [item("aaaaaa111111", "ก.pdf"), item("bbbbbb222222", "ก.pdf")]})
    written, warnings = drive.mirror_folder(client, "root", tmp_path)
    assert len(written) == 2
    assert len({p.name for p in written}) == 2
    assert len(warnings) == 1
    assert "ชื่อไฟล์ซ้ำ" in warnings[0]
    for path in written:
        assert path.exists()


def test_ไฟล์เดียวพังไม่ล้มทั้งรอบ(tmp_path):
    client = FakeDrive({"root": [item("f1", "ก.pdf"), item("f2", "ข.pdf")]}, fail_ids=["f1"])
    written, warnings = drive.mirror_folder(client, "root", tmp_path)
    assert [p.name for p in written] == ["ข.pdf"]
    assert len(warnings) == 1
    assert "ดาวน์โหลดไม่สำเร็จ" in warnings[0]
    assert not (tmp_path / "ก.pdf").exists()


def test_โฟลเดอร์ว่าง(tmp_path):
    written, warnings = drive.mirror_folder(FakeDrive({"root": []}), "root", tmp_path)
    assert (written, warnings) == ([], [])


def test_สร้างโฟลเดอร์ปลายทางให้เองถ้ายังไม่มี(tmp_path):
    dest = tmp_path / "ยังไม่มี" / "ลึกอีกชั้น"
    client = FakeDrive({"root": [item("f1", "ก.pdf")]})
    written, _ = drive.mirror_folder(client, "root", dest)
    assert written[0].exists()


def test_driveclient_ต้องการ_credential_จริง(tmp_path):
    """สร้าง DriveClient โดยชี้ไปไฟล์ที่ไม่มีอยู่ ต้อง error ไม่ใช่เงียบ"""
    with pytest.raises(Exception):
        drive.DriveClient(str(tmp_path / "ไม่มีไฟล์นี้.json"))
