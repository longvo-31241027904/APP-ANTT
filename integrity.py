"""Kiểm kê dữ liệu và tính SHA-256."""

from dataclasses import dataclass
from hashlib import sha256
from ntpath import isreserved
from pathlib import Path
import stat


class AppError(Exception):
    pass


def path_parts(name: str) -> tuple[str, ...]:
    parts = tuple(name.split("/"))
    for part in parts:
        if (
            part in {"", ".", ".."}
            or ":" in part
            or "\\" in part
            or isreserved(part)
            or len(part.encode("utf-16-le")) > 510
        ):
            raise AppError("Có đường dẫn không hợp lệ hoặc không an toàn trên Windows.")
    return parts


def source_type(path: Path) -> bool:
    """Trả về True cho thư mục. Chỉ chấp nhận mục thông thường."""
    info = path.lstat()
    if getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise AppError(f"Nguồn chứa liên kết hoặc điểm phân tích lại: {path}")
    if stat.S_ISDIR(info.st_mode):
        return True
    if stat.S_ISREG(info.st_mode):
        return False
    raise AppError(f"Loại mục nguồn không được hỗ trợ: {path}")


@dataclass(frozen=True)
class FileDigest:
    size: int
    sha256: str


def hash_file(path: Path) -> FileDigest:
    digest = sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    return FileDigest(size, digest.hexdigest())


def inventory(source: Path) -> tuple[dict[str, Path], dict[str, Path]]:
    directories, files = {}, {}
    pending = [(source.name, source)]
    seen = set()
    while pending:
        name, path = pending.pop()
        path_parts(name)
        key = name.casefold()
        if key in seen:
            raise AppError("Nguồn có các tên trùng nhau khi so sánh trên Windows.")
        seen.add(key)
        if source_type(path):
            directories[name] = path
            children = sorted(path.iterdir(), key=lambda child: child.name)
            pending.extend((f"{name}/{child.name}", child) for child in reversed(children))
        else:
            files[name] = path
    return directories, files
