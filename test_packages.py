"""Kiểm thử tích hợp bằng tệp thật trong workspace, dùng mật khẩu ngẫu nhiên trong RAM."""

import json
import os
from pathlib import Path
from secrets import token_urlsafe
import subprocess
from tempfile import TemporaryDirectory
import unittest

import py7zr

from integrity import AppError, hash_file, path_parts
from packages import FILTERS, FORMAT, MANIFEST, archive_layout, create_package, restore_package


class PackageTests(unittest.TestCase):
    def setUp(self):
        scratch = TemporaryDirectory(prefix=".antt-test-", dir=Path(__file__).resolve().parent)
        self.addCleanup(scratch.cleanup)
        self.base = Path(scratch.name)
        self.package = self.base / "Gói thử.7z"
        self.destination = self.base / "Kết quả"
        self.password = token_urlsafe(24) + " Việt"
        self.source = self.base / "Dữ liệu nguồn.txt"
        self.source.write_text("Nội dung kiểm thử SHA-256.\n", encoding="utf-8")

    def create(self, source=None, progress=lambda _: None):
        return create_package(source or self.source, self.package, self.password, progress)

    def restore(self, password=None, progress=lambda _: None):
        return restore_package(self.package, self.destination, password or self.password, progress)

    def assert_clean(self):
        self.assertFalse(list(self.base.glob(".antt-*")))

    def assert_restore_error(self, message, password=None):
        with self.assertRaisesRegex(AppError, message):
            self.restore(password)
        self.assertFalse(self.destination.exists())
        self.assert_clean()

    def write_fixture(self, members, manifest):
        with py7zr.SevenZipFile(
            self.package, "x", password=self.password, header_encryption=True, filters=FILTERS,
        ) as archive:
            for name, content in members:
                archive.writestr(content, name)
            archive.writestr(json.dumps(manifest), MANIFEST)

    def test_single_file(self):
        before = hash_file(self.source)
        self.assertEqual(self.create().count, 1)
        self.assertEqual(self.restore().count, 1)
        self.assertEqual(hash_file(self.source), before)
        self.assertEqual(hash_file(self.destination / self.source.name), before)
        self.assert_clean()

    def test_nested_unicode_and_empty_entries(self):
        source = self.base / "Bộ dữ liệu"
        subfolder = source / "Thư mục con"
        subfolder.mkdir(parents=True)
        (subfolder / "Rỗng").mkdir()
        fixture = {
            "Thư mục con/Ảnh thử.bin": bytes(range(256)),
            "Thư mục con/Tệp rỗng.txt": b"",
            "manifest.json": b"User file with same name as internal manifest",
        }
        for name, content in fixture.items():
            (source / name).write_bytes(content)
        self.assertEqual(self.create(source).count, 3)
        self.assertEqual(self.restore().count, 3)
        restored = self.destination / source.name
        self.assertTrue((restored / "Thư mục con" / "Rỗng").is_dir())
        for name, content in fixture.items():
            self.assertEqual((source / name).read_bytes(), content)
            self.assertEqual((restored / name).read_bytes(), content)
        self.assert_clean()

    def test_empty_source_directory(self):
        folder = self.base / "Thư mục rỗng"
        folder.mkdir()
        self.assertEqual(self.create(folder).count, 0)
        self.assertEqual(self.restore().count, 0)
        self.assertEqual(list((self.destination / folder.name).iterdir()), [])

    def test_wrong_password(self):
        self.create()
        self.assert_restore_error("Mật khẩu có thể sai", token_urlsafe(24))

    def test_corrupt_archive(self):
        self.create()
        with self.package.open("r+b") as stream:
            stream.truncate(40)
        self.assert_restore_error("Mật khẩu có thể sai")

    def test_manifest_hash_size_and_file_list(self):
        name = "data/demo.txt"
        digest = hash_file(self.source)
        correct = {"path": "demo.txt", "size": digest.size, "sha256": digest.sha256}
        for records, members in (
            ([dict(correct, sha256="0" * 64)], [(name, self.source.read_bytes())]),
            ([dict(correct, size=0)], [(name, self.source.read_bytes())]),
            ([dict(correct, path="missing.txt")], [(name, self.source.read_bytes())]),
            ([], [(name, self.source.read_bytes())]),
        ):
            with self.subTest(records=records):
                manifest = {"format": FORMAT, "directories": [], "files": records}
                self.write_fixture(members, manifest)
                self.assert_restore_error("không khớp manifest")
                self.package.unlink()

    def test_unsafe_names_and_duplicate(self):
        for path in ("/absolute", "C:/absolute", "../escape", "data/../../escape",
                     "data/CON.txt", "data/f.txt:alternate", "data/trailing."):
            with self.subTest(path=path), self.assertRaises(AppError):
                path_parts(path)
        for members, message in (
            ([("data/CON.txt", b"sample")], "không an toàn"),
            ([("data/A.txt", b"sample"), ("data/a.txt", b"sample")], "trùng nhau"),
        ):
            with self.subTest(members=members):
                self.write_fixture(members, {})
                steps = []
                with self.assertRaisesRegex(AppError, message):
                    self.restore(progress=steps.append)
                self.assertEqual(steps, ["Đọc gói và kiểm tra tên mục…"])
                self.assertFalse(self.destination.exists())
                self.assert_clean()
                self.package.unlink()

    def test_unverified_member_type(self):
        self.write_fixture([("data/demo.txt", b"sample")], {})
        # Mô phỏng metadata không đủ để kiểm tra kiểu mục, trước khi giải nén.
        with py7zr.SevenZipFile(self.package, password=self.password) as archive:
            archive.files[0].file_properties().pop("attributes")
            with self.assertRaisesRegex(AppError, "chưa xác minh"):
                archive_layout(archive)

    def test_existing_destinations(self):
        self.package.write_bytes(b"existing")
        with self.assertRaisesRegex(AppError, "Đích đã tồn tại"):
            self.create()
        self.assertEqual(self.package.read_bytes(), b"existing")
        self.package.unlink()
        self.create()
        self.destination.mkdir()
        marker = self.destination / "giữ lại.txt"
        marker.write_bytes(b"existing")
        with self.assertRaisesRegex(AppError, "Đích đã tồn tại"):
            self.restore()
        self.assertEqual(list(self.destination.iterdir()), [marker])
        self.assertEqual(marker.read_bytes(), b"existing")
        self.assert_clean()

    def test_destination_appears_while_working(self):
        def occupy_archive(step):
            if step.startswith("Công bố"):
                self.package.write_bytes(b"new file from another process")

        with self.assertRaisesRegex(AppError, "Đích đã tồn tại"):
            self.create(progress=occupy_archive)
        self.assertEqual(self.package.read_bytes(), b"new file from another process")
        self.assert_clean()
        self.package.unlink()
        self.create()

        def occupy_restore(step):
            if step.startswith("Công bố"):
                self.destination.mkdir()

        with self.assertRaisesRegex(AppError, "Đích đã tồn tại"):
            self.restore(progress=occupy_restore)
        self.assertEqual(list(self.destination.iterdir()), [])
        self.assert_clean()

    def test_destination_inside_source(self):
        folder = self.base / "Nguồn"
        folder.mkdir()
        with self.assertRaisesRegex(AppError, "bên ngoài thư mục nguồn"):
            create_package(folder, folder / "Gói.7z", self.password, lambda _: None)
        self.assertEqual(list(folder.iterdir()), [])

    def test_source_changes_after_hashing(self):
        def change_source(step):
            if step.startswith("Nén và mã hóa"):
                self.source.write_bytes(b"source updated independently")

        with self.assertRaisesRegex(AppError, "không khớp manifest"):
            self.create(progress=change_source)
        self.assertEqual(self.source.read_bytes(), b"source updated independently")
        self.assertFalse(self.package.exists())
        self.assert_clean()

    def test_independent_7zip(self):
        exe = Path(os.environ["ProgramFiles"]) / "7-Zip" / "7z.exe"
        if not exe.is_file():
            self.skipTest("Thiếu 7-Zip độc lập tại đường dẫn cài đặt mặc định.")
        self.password = token_urlsafe(24)
        self.create()
        name = self.source.name.encode("utf-8")
        password_line = (self.password + "\n").encode("ascii")

        def run(*args, stdin):
            return subprocess.run(
                [exe, *args, "-sccUTF-8", self.package], input=stdin,
                capture_output=True, timeout=20,
            )

        locked = run("l", stdin=b"\n")
        self.assertNotEqual(locked.returncode, 0)
        self.assertNotIn(name, locked.stdout + locked.stderr)
        self.assertNotIn(MANIFEST.encode(), locked.stdout + locked.stderr)
        listing = run("l", "-slt", stdin=password_line)
        self.assertEqual(listing.returncode, 0)
        self.assertIn(name, listing.stdout)
        self.assertIn(b"7zAES", listing.stdout)
        self.assertEqual(run("t", stdin=password_line).returncode, 0)


if __name__ == "__main__":
    unittest.main()
