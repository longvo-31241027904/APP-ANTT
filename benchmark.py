"""Phép đo ghép cặp cho Store và LZMA2 trên cùng bộ dữ liệu."""

import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, stdev
from tempfile import TemporaryDirectory
from time import perf_counter

from integrity import AppError, source_type
from packages import COMPRESSION, LZMA2_PRESET, Progress, source_manifest, verify_archive, write_archive

MIB = 1024 ** 2
PHASES = {"create_seconds": "Tạo gói", "restore_seconds": "Khôi phục", "verify_seconds": "Kiểm SHA-256"}


@dataclass
class Trial:
    pair: str
    compression: str
    configuration: str
    order: int
    source_bytes: int
    package_bytes: int | None = None
    create_seconds: float | None = None
    restore_seconds: float | None = None
    verify_seconds: float | None = None
    checked: int | None = None
    matched: int | None = None
    sha256: str = "Chưa xác minh"
    status: str = "Lỗi"
    reason: str = ""


def benchmark(source: Path, pairs: int, password: str, progress: Progress) -> list[Trial]:
    if not password or pairs < 1:
        raise AppError("Cần mật khẩu thử và ít nhất một cặp đo.")
    source_type(source)
    source = source.resolve(strict=True)
    directories, files, manifest = source_manifest(source, progress)
    source_bytes = sum(row["size"] for row in manifest["files"])
    trials = []
    with TemporaryDirectory(prefix="safepack-measure-") as workspace:
        if Path(workspace).resolve().is_relative_to(source):
            raise AppError("Hãy chọn một bộ mẫu nằm ngoài thư mục tạm của phiên đo.")
        for compression, label in COMPRESSION.items():
            for pair in range(1, pairs + 1):
                order = (False, True) if pair % 2 else (True, False)
                for position, encrypted in enumerate(order, 1):
                    label_crypto = "AES-256 + ẩn tên" if encrypted else "Đối chứng"
                    trial = Trial(f"{compression}-{pair:02}", compression, label_crypto, position, source_bytes)
                    trials.append(trial)

                    def step(message: str):
                        progress(f"{label} · cặp {pair}/{pairs} · {label_crypto} — {message}")

                    timings: dict[str, float | int] = {}
                    with TemporaryDirectory(dir=workspace) as folder:
                        staging = Path(folder)
                        archive = staging / "sample.7z"
                        secret = password if encrypted else None
                        try:
                            started = perf_counter()
                            write_archive(archive, directories, files, manifest, secret, compression, step)
                            trial.create_seconds = perf_counter() - started
                            trial.package_bytes = archive.stat().st_size
                            actual = verify_archive(archive, secret, staging, True, step, timings=timings)
                            if actual != manifest:
                                raise AppError("Gói khôi phục khác bản kiểm kê nguồn ban đầu.")
                        except AppError as error:
                            trial.reason = str(error).replace(password, "[đã ẩn]")
                            if timings.get("checked") is not None:
                                trial.sha256 = "Không đạt"
                        except OSError:
                            trial.reason = "Lỗi đọc/ghi. Kiểm tra quyền truy cập và dung lượng thư mục tạm."
                        except Exception:
                            trial.reason = "Không hoàn tất được thao tác với gói 7-Zip."
                        else:
                            trial.sha256 = "Khớp"
                            trial.status = "Đạt"
                        for field, value in timings.items():
                            setattr(trial, field, value)
    return trials


def valid_pairs(trials: list[Trial], compression: str) -> list[tuple[Trial, Trial]]:
    grouped = {}
    for trial in trials:
        if trial.compression == compression:
            grouped.setdefault(trial.pair, {})[trial.configuration] = trial
    pairs = []
    for entries in grouped.values():
        control = entries.get("Đối chứng")
        encrypted = entries.get("AES-256 + ẩn tên")
        if control and encrypted and control.status == encrypted.status == "Đạt":
            pairs.append((control, encrypted))
    return pairs


def summarize(trials: list[Trial], compression: str) -> dict:
    pairs = valid_pairs(trials, compression)
    if not pairs:
        return {"pairs": 0}
    summary = {"pairs": len(pairs), "phases": {}}
    measurements = list(PHASES) + ["package_bytes"]
    for field in measurements:
        control = [getattr(pair[0], field) for pair in pairs]
        encrypted = [getattr(pair[1], field) for pair in pairs]
        averages = (mean(control), mean(encrypted))
        if field == "package_bytes":
            summary["package_bytes"] = averages
            summary["savings"] = tuple(
                mean(100 * (1 - trial.package_bytes / trial.source_bytes) for trial in group)
                if group[0].source_bytes else None
                for group in zip(*pairs)
            )
            continue
        summary["phases"][field] = {
            "averages": averages,
            "throughput": tuple(pairs[0][0].source_bytes / MIB / value if value else None for value in averages),
            "delta_stdev": stdev(b - a for a, b in zip(control, encrypted)) if len(pairs) >= 2 else None,
            "overhead": 100 * (averages[1] - averages[0]) / averages[0] if averages[0] else None,
        }
    return summary


def recommend_mode(trials: list[Trial], byte_limit: float) -> tuple[str, float, int, int] | None:
    candidates = []
    for mode in COMPRESSION:
        encrypted = [
            trial for trial in trials
            if trial.compression == mode and trial.configuration == "AES-256 + ẩn tên" and trial.status == "Đạt"
        ]
        if not encrypted:
            continue
        largest = max(trial.package_bytes for trial in encrypted)
        if largest <= byte_limit:
            candidates.append((mean(trial.create_seconds for trial in encrypted), mode, largest, len(encrypted)))
    if not candidates:
        return None
    seconds, mode, largest, count = min(candidates)
    return mode, seconds, largest, count


def export_trials(path: Path, trials: list[Trial]) -> None:
    rows = [
        {**asdict(trial), "lzma2_preset": LZMA2_PRESET if trial.compression == "LZMA2" else ""}
        for trial in trials
    ]
    if not rows:
        raise AppError("Chưa có lượt đo để xuất.")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
