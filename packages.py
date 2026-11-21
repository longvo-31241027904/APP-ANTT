"""Định dạng gói ANTT v1 và hai luồng xử lý chạy trên Windows."""

from collections.abc import Callable
from dataclasses import asdict, dataclass
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import stat
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import BinaryIO

import py7zr
from py7zr.io import Py7zIO, WriterFactory
from py7zr.member import FILE_ATTRIBUTE_UNIX_EXTENSION

from integrity import AppError, FileDigest, hash_file, inventory, path_parts, source_type


MANIFEST = "manifest.json"
DATA = "data"
FORMAT = "APP ANTT CKI/1"
MANIFEST_LIMIT = 32 * 1024 * 1024
LZMA2_PRESET = 1
COMPRESSION = {"Store": "Store (không nén)", "LZMA2": f"LZMA2 (preset {LZMA2_PRESET})"}
AES = {"id": py7zr.FILTER_CRYPTO_AES256_SHA256}
FILTERS = [{"id": py7zr.FILTER_LZMA2, "preset": LZMA2_PRESET}, AES]
READ_ERROR = "Không đọc được gói .7z. Mật khẩu có thể sai hoặc gói bị lỗi."
Progress = Callable[[str], None]


@dataclass(frozen=True)
class Result:
    path: Path
    count: int
    seconds: float


def archive_layout(archive: py7zr.SevenZipFile) -> tuple[set[str], dict[str, int]]:
    directories, sizes, seen = set(), {}, set()
    for member in archive.files:
        name = member.filename
        parts = path_parts(name)
        key = name.casefold()
        if key in seen:
            raise AppError("Gói chứa các mục có tên trùng nhau trên Windows.")
        seen.add(key)
        attributes = member.file_properties().get("attributes")
        if (
            attributes is None
            or not attributes & FILE_ATTRIBUTE_UNIX_EXTENSION
            or attributes & (stat.FILE_ATTRIBUTE_REPARSE_POINT | stat.FILE_ATTRIBUTE_DEVICE)
        ):
            raise AppError("Gói chứa liên kết hoặc loại mục chưa xác minh được.")
        mode = attributes >> 16
        is_directory = member.is_directory
        valid_type = stat.S_ISDIR(mode) if is_directory else stat.S_ISREG(mode)
        if not valid_type or member.is_symlink or member.is_junction or member.is_socket:
            raise AppError("Gói chứa liên kết hoặc loại mục chưa xác minh được.")
        if (name != MANIFEST) and (len(parts) < 2 or parts[0] != DATA):
            raise AppError("Gói có cấu trúc khác định dạng APP ANTT CKI.")
        if is_directory:
            if not member.emptystream:
                raise AppError("Gói chứa mục thư mục không hợp lệ.")
            directories.add(name)
        else:
            if type(member.uncompressed) is not int or member.uncompressed < 0:
                raise AppError("Gói chứa tệp có kích thước không hợp lệ.")
            sizes[name] = member.uncompressed

    if MANIFEST not in sizes or not 0 < sizes[MANIFEST] <= MANIFEST_LIMIT:
        raise AppError("Manifest bị thiếu hoặc có kích thước không hợp lệ.")
    roots = set()
    for name in (directories | sizes.keys()) - {MANIFEST}:
        parts = name.split("/")
        roots.add(parts[1])
        if len(parts) > 2 and name.rsplit("/", 1)[0] not in directories:
            raise AppError("Gói chứa mục có thư mục cha không hợp lệ.")
    if len(roots) != 1:
        raise AppError("Gói phải chứa đúng một tệp hoặc thư mục nguồn.")
    return directories, sizes


class CheckedWriter(Py7zIO):
    def __init__(self, name: str, factory: "CheckedFactory", stream: BinaryIO | None):
        self.name = name
        self.factory = factory
        self.stream = stream
        self.digest = sha256() if stream is None else None
        self.count = 0

    def write(self, data: bytes | bytearray) -> int:
        if self.count + len(data) > self.factory.sizes[self.name]:
            raise AppError("Dữ liệu giải nén vượt quá kích thước khai báo trong gói.")
        if self.stream is not None:
            self.stream.write(data)
        if self.digest is not None:
            self.digest.update(data)
        self.count += len(data)
        return len(data)

    def read(self, size: int | None = None) -> bytes:
        raise OSError("Luồng giải nén chỉ hỗ trợ ghi.")

    def seek(self, offset: int, whence: int = 0) -> int:
        raise OSError("Luồng giải nén không hỗ trợ đổi vị trí.")

    def seekable(self) -> bool:
        return False

    def flush(self) -> None:
        if self.stream is not None:
            self.stream.flush()

    def size(self) -> int:
        return self.count

    def close(self) -> None:
        if self.name != MANIFEST and self.stream is not None:
            self.stream.close()
        digest = self.digest.hexdigest() if self.digest is not None else ""
        self.factory.digests[self.name] = FileDigest(self.count, digest)
        del self.factory.active[self.name]


class CheckedFactory(WriterFactory):
    def __init__(self, root: Path, sizes: dict[str, int], save_data: bool):
        self.paths = {root.joinpath(*name.split("/")).as_posix(): name for name in sizes}
        self.sizes = sizes
        self.save_data = save_data
        self.manifest = BytesIO()
        self.digests: dict[str, FileDigest] = {}
        self.active: dict[str, CheckedWriter] = {}

    def create(self, filename: str) -> CheckedWriter:
        name = self.paths.get(filename)
        if name is None or name in self.digests or name in self.active:
            raise AppError("Gói yêu cầu ghi một mục ngoài danh sách đã kiểm tra.")
        stream = None
        if name == MANIFEST:
            stream = self.manifest
        elif self.save_data:
            stream = Path(filename).open("xb")
        writer = CheckedWriter(name, self, stream)
        self.active[name] = writer
        return writer

    def close(self) -> None:
        for writer in self.active.values():
            if writer.stream is not None and writer.stream is not self.manifest:
                writer.stream.close()
        self.manifest.close()


def manifest_payload(directories: set[str], digests: dict[str, FileDigest]) -> dict:
    return {
        "format": FORMAT,
        "directories": sorted(directories),
        "files": [{"path": name, **asdict(digests[name])} for name in sorted(digests)],
    }


def read_manifest(raw: bytes) -> dict:
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Khóa bị lặp.")
            result[key] = value
        return result

    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_keys)
        if not isinstance(payload, dict) or set(payload) != {"format", "directories", "files"}:
            raise ValueError
        if payload["format"] != FORMAT or not isinstance(payload["directories"], list):
            raise ValueError
        if not isinstance(payload["files"], list):
            raise ValueError
        for record in payload["files"]:
            if (
                not isinstance(record, dict)
                or set(record) != {"path", "size", "sha256"}
                or not isinstance(record["path"], str)
                or type(record["size"]) is not int
                or record["size"] < 0
                or not isinstance(record["sha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"])
            ):
                raise ValueError
    except (ValueError, RecursionError):
        raise AppError("Manifest không đúng định dạng APP ANTT CKI.") from None
    return payload


def package_manifest(raw: bytes, directories: set[str], sizes: dict[str, int]) -> dict:
    manifest = read_manifest(raw)
    declared = {row["path"]: row["size"] for row in manifest["files"]}
    if (
        manifest["directories"] != sorted(name.removeprefix(f"{DATA}/") for name in directories)
        or len(declared) != len(manifest["files"])
        or declared != {name.removeprefix(f"{DATA}/"): size for name, size in sizes.items() if name != MANIFEST}
    ):
        raise AppError("Danh sách mục hoặc kích thước không khớp manifest.")
    return manifest


def decode_members(
    archive: py7zr.SevenZipFile,
    staging: Path,
    sizes: dict[str, int],
    save_data: bool,
) -> tuple[bytes, dict[str, FileDigest]]:
    writer = CheckedFactory(staging, sizes, save_data)
    try:
        archive.extract(path=staging, targets=list(sizes), factory=writer)
        if {name: value.size for name, value in writer.digests.items()} != sizes:
            raise AppError("Số tệp hoặc kích thước dữ liệu không khớp với gói.")
        return writer.manifest.getvalue(), writer.digests
    finally:
        writer.close()


def inspect_package(package: Path, password: str, progress: Progress) -> dict:
    if not password:
        raise AppError("Hãy nhập mật khẩu của gói.")
    progress("Mở gói và đọc manifest…")
    try:
        with py7zr.SevenZipFile(package, "r", password=password) as archive:
            if not archive.needs_password():
                raise AppError("Gói này không được mã hóa.")
            directories, sizes = archive_layout(archive)
            archive.max_extract_size = sum(sizes.values())
            with TemporaryDirectory(prefix=".antt-") as workspace:
                raw, _ = decode_members(archive, Path(workspace), {MANIFEST: sizes[MANIFEST]}, False)
            return package_manifest(raw, directories, sizes)
    except (AppError, OSError):
        raise
    except Exception:
        raise AppError(READ_ERROR) from None


def verify_archive(
    package: Path,
    password: str | None,
    staging: Path,
    save_data: bool,
    progress: Progress,
    *,
    selection: set[str] | None = None,
    timings: dict[str, float | int] | None = None,
    opened_manifest: dict | None = None,
) -> dict:
    progress("Đọc gói và kiểm tra tên mục…")
    started = perf_counter()
    try:
        with py7zr.SevenZipFile(package, "r", password=password) as archive:
            directories, sizes = archive_layout(archive)
            archive.max_extract_size = sum(sizes.values())
            targets = sizes
            if selection is not None:
                selected_members = {f"{DATA}/{name}" for name in selection}
                if not selection or not selected_members <= sizes.keys():
                    raise AppError("Một hoặc nhiều tệp được chọn không có trong gói.")
                targets = {name: sizes[name] for name in selected_members | {MANIFEST}}
            if save_data:
                (staging / DATA).mkdir()
                if selection is None:
                    for name in sorted(directories):
                        staging.joinpath(*name.split("/")).mkdir()
                else:
                    for name in selected_members:
                        staging.joinpath(*name.split("/")).parent.mkdir(parents=True, exist_ok=True)
            progress("Giải nén vào thư mục tạm…" if save_data else "Đọc và tính SHA-256 từ gói…")
            raw, digests = decode_members(archive, staging, targets, save_data)
    except (AppError, OSError):
        raise
    except Exception:
        raise AppError(READ_ERROR) from None

    if timings is not None:
        timings["restore_seconds"] = perf_counter() - started
    progress("Đối chiếu manifest và SHA-256…")
    started = perf_counter()
    manifest = package_manifest(raw, directories, sizes)
    if opened_manifest is not None and opened_manifest != manifest:
        raise AppError("Nội dung gói đã thay đổi. Hãy mở lại gói để lấy danh sách hiện tại.")
    expected = {
        row["path"]: FileDigest(row["size"], row["sha256"])
        for row in manifest["files"] if selection is None or row["path"] in selection
    }
    if save_data:
        roots = list((staging / DATA).iterdir())
        if len(roots) != 1:
            raise AppError("Số mục nguồn trên ổ đĩa không khớp với gói.")
        restored_dirs, restored_files = inventory(roots[0])
        if selection is None and set(restored_dirs) != {name.removeprefix(f"{DATA}/") for name in directories}:
            raise AppError("Cấu trúc thư mục đã ghi không khớp với gói.")
        actual = {name: hash_file(path) for name, path in restored_files.items()}
    else:
        actual = {
            name.removeprefix(f"{DATA}/"): digest
            for name, digest in digests.items() if name != MANIFEST
        }
    if timings is not None:
        timings["checked"] = len(actual)
        timings["matched"] = sum(expected.get(name) == digest for name, digest in actual.items())
        timings["verify_seconds"] = perf_counter() - started
    if actual != expected:
        raise AppError("Danh sách tệp, kích thước hoặc SHA-256 không khớp manifest.")
    return manifest


def check_package(
    package: Path, password: str, progress: Progress, *, opened_manifest: dict | None = None
) -> Result:
    started = perf_counter()
    with TemporaryDirectory(prefix=".antt-") as workspace:
        manifest = verify_archive(package, password, Path(workspace), False, progress, opened_manifest=opened_manifest)
    return Result(package, len(manifest["files"]), perf_counter() - started)


DIFF_GROUPS = ("Còn nguyên", "Đã sửa", "Mới thêm", "Bị thiếu")


def compare_folder(manifest: dict, folder: Path, progress: Progress) -> list[tuple[str, str]]:
    if not source_type(folder):
        raise AppError("Hãy chọn một thư mục để so sánh.")
    progress("Kiểm kê và tính SHA-256 của thư mục hiện tại…")
    _, files = inventory(folder)
    actual = {name.split("/", 1)[1].casefold(): (name.split("/", 1)[1], path) for name, path in files.items()}
    is_directory = bool(manifest["directories"])
    rows = []
    for entry in manifest["files"]:
        name = entry["path"].split("/", 1)[1] if is_directory else entry["path"]
        found = actual.pop(name.casefold(), None)
        if found is None:
            status = "Bị thiếu"
        elif hash_file(found[1]).sha256 == entry["sha256"]:
            status = "Còn nguyên"
        else:
            status = "Đã sửa"
        rows.append((name, status))
    rows.extend((name, "Mới thêm") for name, _ in actual.values())
    return sorted(rows, key=lambda row: row[0].casefold())


def require_absent(path: Path) -> None:
    try:
        path.lstat()
    except FileNotFoundError:
        return
    raise AppError(f"Đích đã tồn tại: {path}")


def publish(temporary: Path, destination: Path) -> None:
    # Trên Windows, rename cùng ổ thất bại nếu đích đã xuất hiện.
    try:
        temporary.rename(destination)
    except FileExistsError:
        raise AppError(f"Đích đã tồn tại: {destination}") from None


def source_manifest(source: Path, progress: Progress) -> tuple[dict[str, Path], dict[str, Path], dict]:
    progress("Kiểm kê nguồn và tính SHA-256…")
    directories, files = inventory(source)
    digests = {name: hash_file(path) for name, path in files.items()}
    return directories, files, manifest_payload(set(directories), digests)


def write_archive(
    temporary: Path,
    directories: dict[str, Path],
    files: dict[str, Path],
    manifest: dict,
    password: str | None,
    compression: str,
    progress: Progress,
) -> None:
    raw = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
    if len(raw) > MANIFEST_LIMIT:
        raise AppError("Manifest vượt giới hạn 32 MiB của ứng dụng.")
    filters = [{"id": py7zr.FILTER_COPY}] if compression == "Store" else FILTERS[:1]
    if password:
        filters.append(AES)
    progress("Nén và mã hóa bằng AES-256…" if password else "Tạo gói đối chứng…")
    with py7zr.SevenZipFile(
        temporary, "x", password=password, header_encryption=bool(password), filters=filters
    ) as archive:
        for name, folder in directories.items():
            if not source_type(folder):
                raise AppError("Loại mục nguồn đã thay đổi trong lúc tạo gói.")
            archive.write(folder, f"{DATA}/{name}")
        for name, path in files.items():
            if source_type(path):
                raise AppError("Loại mục nguồn đã thay đổi trong lúc tạo gói.")
            archive.write(path, f"{DATA}/{name}")
        archive.writestr(raw, MANIFEST)


def create_package(
    source: Path, output: Path, password: str, progress: Progress, *, compression: str = "LZMA2"
) -> Result:
    path_parts(output.name)
    if not password or output.suffix.lower() != ".7z":
        raise AppError("Cần nhập mật khẩu và đặt tên gói có đuôi .7z.")
    if compression not in COMPRESSION:
        raise AppError("Chế độ nén không được hỗ trợ.")
    source_is_directory = source_type(source)
    source = source.resolve(strict=True)
    output = output.parent.resolve(strict=True) / output.name
    require_absent(output)
    if source_is_directory and output.is_relative_to(source):
        raise AppError("Hãy chọn nơi lưu gói bên ngoài thư mục nguồn.")

    started = perf_counter()
    directories, files, manifest = source_manifest(source, progress)
    with TemporaryDirectory(prefix=".antt-", dir=output.parent) as workspace:
        staging = Path(workspace)
        temporary = staging / "package.7z"
        write_archive(temporary, directories, files, manifest, password, compression, progress)
        if verify_archive(temporary, password, staging, False, progress) != manifest:
            raise AppError("Gói tạm không khớp với bản kiểm kê nguồn.")
        progress("Công bố gói .7z…")
        publish(temporary, output)
        seconds = perf_counter() - started
    return Result(output, len(files), seconds)


def restore_package(
    package: Path,
    destination: Path,
    password: str,
    progress: Progress,
    *,
    selection: set[str] | None = None,
    opened_manifest: dict | None = None,
) -> Result:
    if len(path_parts(destination.name)) != 1:
        raise AppError("Hãy nhập một tên thư mục duy nhất.")
    if not password:
        raise AppError("Hãy nhập mật khẩu của gói.")
    destination = destination.parent.resolve(strict=True) / destination.name
    require_absent(destination)
    started = perf_counter()
    with TemporaryDirectory(prefix=".antt-", dir=destination.parent) as workspace:
        staging = Path(workspace)
        manifest = verify_archive(
            package.resolve(strict=True), password, staging, True, progress,
            selection=selection, opened_manifest=opened_manifest,
        )
        progress("Công bố thư mục dữ liệu đã kiểm tra…")
        publish(staging / DATA, destination)
        seconds = perf_counter() - started
    return Result(destination, len(manifest["files"]) if selection is None else len(selection), seconds)
