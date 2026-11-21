import csv
import json
from pathlib import Path
from secrets import token_urlsafe
from tempfile import TemporaryDirectory
import unittest

import py7zr

from benchmark import benchmark, export_trials, recommend_mode, summarize
from integrity import AppError
from packages import (
    DATA, FILTERS, MANIFEST, check_package, compare_folder, inspect_package,
    restore_package, source_manifest,
)


class SafePackTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "Mẫu"
        (self.source / "Tệp con").mkdir(parents=True)
        self.before = b"original text"
        (self.source / "Tệp con" / "a.txt").write_bytes(self.before)
        (self.source / "b.txt").write_bytes(b"csv,example\n" * 4000)
        (self.source / "c.txt").touch()
        self.secret = token_urlsafe(24)

    def test_paired_benchmark_and_export(self):
        rows = benchmark(self.source, 2, self.secret, lambda _: None)
        self.assertEqual(len(rows), 8)
        for mode in ("Store", "LZMA2"):
            group = [row for row in rows if row.compression == mode]
            self.assertEqual([row.configuration for row in group], [
                "Đối chứng", "AES-256 + ẩn tên", "AES-256 + ẩn tên", "Đối chứng",
            ])
            self.assertTrue(all(row.status == "Đạt" and row.checked == row.matched == 3 for row in group))
            stats = summarize(rows, mode)
            self.assertEqual(stats["pairs"], 2)
            self.assertIsNotNone(stats["phases"]["create_seconds"]["delta_stdev"])

        self.assertIsNone(recommend_mode(rows, 0))
        choice = recommend_mode(rows, 20 * 1024 * 1024)
        self.assertIsNotNone(choice)
        mode, _, largest, count = choice
        encrypted = [row for row in rows if row.compression == mode and row.configuration != "Đối chứng"]
        self.assertEqual(largest, max(row.package_bytes for row in encrypted))
        self.assertEqual(count, 2)
        csv_file = self.root / "Ngay đo.csv"
        export_trials(csv_file, rows)
        self.assertNotIn(self.secret, csv_file.read_text(encoding="utf-8-sig"))
        with csv_file.open(encoding="utf-8-sig", newline="") as stream:
            records = list(csv.DictReader(stream))
        self.assertEqual({(row["compression"], row["configuration"]) for row in records}, {
            (mode, configuration) for mode in ("Store", "LZMA2") for configuration in ("Đối chứng", "AES-256 + ẩn tên")
        })
        self.assertTrue(all(row["sha256"] == "Khớp" for row in records))

    def test_legacy_v1_diff_and_selective_restore(self):
        package = self.root / "Gói cũ.7z"
        progress = lambda _: None
        directories, files, manifest = source_manifest(self.source, progress)
        self.assertEqual(manifest["format"], "APP ANTT CKI/1")
        with py7zr.SevenZipFile(package, "x", password=self.secret, header_encryption=True, filters=FILTERS) as archive:
            for name, path in (*directories.items(), *files.items()):
                archive.write(path, f"{DATA}/{name}")
            archive.writestr(json.dumps(manifest, ensure_ascii=False), MANIFEST)

        with self.assertRaisesRegex(AppError, "Mật khẩu có thể sai"):
            inspect_package(package, token_urlsafe(24), progress)
        self.assertEqual(inspect_package(package, self.secret, progress), manifest)
        self.assertEqual(check_package(package, self.secret, progress).count, 3)
        (self.source / "Tệp con" / "a.txt").write_bytes(b"updated text!")
        (self.source / "c.txt").unlink()
        (self.source / "d.txt").write_bytes(b"added")
        self.assertEqual(dict(compare_folder(manifest, self.source, progress)), {
            "Tệp con/a.txt": "Đã sửa", "b.txt": "Còn nguyên", "c.txt": "Bị thiếu", "d.txt": "Mới thêm",
        })

        destination = self.root / "Khôi phục"
        selected = {"Mẫu/Tệp con/a.txt", "Mẫu/c.txt"}
        result = restore_package(package, destination, self.secret, progress, selection=selected)
        self.assertEqual(result.count, 2)
        self.assertEqual((destination / "Mẫu" / "Tệp con" / "a.txt").read_bytes(), self.before)
        self.assertEqual((destination / "Mẫu" / "c.txt").read_bytes(), b"")
        self.assertFalse((destination / "Mẫu" / "b.txt").exists())
        with self.assertRaisesRegex(AppError, "Đích đã tồn tại"):
            restore_package(package, destination, self.secret, progress, selection=selected)
        self.assertEqual(restore_package(package, self.root / "Toàn bộ", self.secret, progress).count, 3)
