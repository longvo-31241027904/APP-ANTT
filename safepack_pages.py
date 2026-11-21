"""Các màn hình đo cấu hình và duyệt nội dung gói của ANTT SafePack."""

from collections import Counter
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDoubleSpinBox, QFileDialog, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QMessageBox, QPushButton, QSpinBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from benchmark import MIB, PHASES, benchmark, export_trials, recommend_mode, summarize
from integrity import AppError, path_parts
from packages import COMPRESSION, DIFF_GROUPS, check_package, compare_folder, inspect_package, restore_package


UNAVAILABLE = "Chưa đủ dữ liệu"


def number(value, suffix="", places=3):
    return UNAVAILABLE if value is None else f"{value:,.{places}f}{suffix}"


def action(layout, title, callback):
    button = QPushButton(title)
    button.clicked.connect(callback)
    layout.addWidget(button)
    return button


def table(headers, *, stretch_last=True):
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.setAlternatingRowColors(True)
    widget.verticalHeader().hide()
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    widget.horizontalHeader().setStretchLastSection(stretch_last)
    return widget


def fill_table(widget, rows):
    widget.setRowCount(len(rows))
    for index, row in enumerate(rows):
        for column, value in enumerate(row):
            item = QTableWidgetItem(str(value))
            item.setToolTip(str(value))
            widget.setItem(index, column, item)


class TaskPage(QWidget):
    def __init__(self, window, mode, title):
        super().__init__()
        self.window = window
        self.mode = mode
        self.source = None
        self.finish = None
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(25, 23, 25, 19)
        self.layout.setSpacing(10)
        heading = QLabel(title)
        heading.setStyleSheet("font-size: 23px; font-weight: 700; color: #162623;")
        self.layout.addWidget(heading)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.layout.addWidget(self.status)

    def start(self, job, finish):
        if self.window.busy:
            return
        self.finish = finish
        self.window.start_task(self, job)

    def show_working(self, title, step):
        self.update_progress_step(step)

    def update_progress_step(self, step):
        self.status.setText(f"Đang xử lý · {step}")

    def show_success_result(self, result):
        finish, self.finish = self.finish, None
        finish(result)

    def show_error_result(self, title, message):
        self.finish = None
        self.status.setText(f"{title}. {message}")


class ComparisonChart(QWidget):
    def __init__(self, size_chart=False):
        super().__init__()
        self.size_chart = size_chart
        self.groups = []
        self.setMinimumHeight(260 if size_chart else 300)

    def set_summaries(self, summaries):
        self.groups = []
        for mode, data in summaries.items():
            if not data["pairs"]:
                continue
            if self.size_chart:
                self.groups.append((mode, tuple(value / MIB for value in data["package_bytes"])))
            else:
                for field, phase in data["phases"].items():
                    self.groups.append((f"{mode} · {PHASES[field]}", phase["averages"]))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#fff"))
        painter.setPen(QColor("#1c3a34"))
        painter.drawText(12, 23, "Trung bình theo cặp hợp lệ · " + ("MiB" if self.size_chart else "giây"))
        if not self.groups:
            painter.drawText(12, 51, UNAVAILABLE)
            return
        painter.setPen(QColor("#567487"))
        painter.drawText(12, 47, "■  Đối chứng")
        painter.setPen(QColor("#10674d"))
        painter.drawText(117, 47, "■  AES-256 + ẩn tên")
        maximum = max(max(values) for _, values in self.groups)
        left = 150
        bar_width = max(1, self.width() - left - 83)
        spacing = min(70, (self.height() - 64) / len(self.groups))
        for index, (label, values) in enumerate(self.groups):
            top = 61 + index * spacing
            painter.setPen(QColor("#1c3a34"))
            painter.drawText(12, int(top + 17), label)
            for bar, (color, value) in enumerate(zip(("#567487", "#10674d"), values)):
                y = top + bar * 16
                width = value / maximum * bar_width if maximum else 0
                painter.fillRect(QRectF(left, y, bar_width, 13), QColor("#eef3f1"))
                painter.fillRect(QRectF(left, y, width, 13), QColor(color))
                painter.drawText(left + bar_width + 6, int(y + 11), f"{value:.5g}")


class BenchmarkPage(TaskPage):
    def __init__(self, window):
        super().__init__(window, "benchmark", "So sánh cấu hình")
        self.trials = []
        self.recommended = None
        self.status.setText(f"Chọn dữ liệu mẫu để đo {COMPRESSION['Store']} và {COMPRESSION['LZMA2']}.")
        source_row = QHBoxLayout()
        action(source_row, "Chọn tệp", self.pick_file)
        action(source_row, "Chọn thư mục", self.pick_folder)
        self.source_label = QLabel("Chưa chọn dữ liệu")
        self.source_label.setTextFormat(Qt.TextFormat.PlainText)
        self.source_label.setWordWrap(True)
        source_row.addWidget(self.source_label, 1)
        self.layout.addLayout(source_row)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Số cặp mỗi chế độ"))
        self.pairs = QSpinBox()
        self.pairs.setRange(1, 100)
        self.pairs.setValue(5)
        self.pairs.valueChanged.connect(self.clear_results)
        controls.addWidget(self.pairs)
        self.run_button = action(controls, "Chạy so sánh", self.run)
        self.run_button.setObjectName("primary")
        self.csv_button = action(controls, "Xuất CSV", self.export)
        controls.addStretch(1)
        self.layout.addLayout(controls)

        self.tabs = QTabWidget()
        self.summary = table([
            "Chế độ", "Cặp đạt", "Công đoạn", "Đối chứng", "AES-256",
            "MiB/s đối chứng", "MiB/s AES", "SD cặp", "Chi phí (%)",
        ])
        self.summary.horizontalHeaderItem(4).setToolTip("AES-256 có mã hóa tên tệp")
        self.summary.horizontalHeaderItem(7).setToolTip("Độ lệch chuẩn mẫu của chênh lệch thời gian từng cặp")
        self.summary.horizontalHeaderItem(8).setToolTip("Chi phí của AES-256 và mã hóa tên tệp so với đối chứng")
        self.details = table([
            "Mã cặp", "Cấu hình", "Thứ tự", "Tạo (s)", "Khôi phục (s)", "SHA-256 (s)",
            "Nguồn (byte)", "Gói (byte)", "Khớp / đã kiểm", "Kết quả SHA-256", "Trạng thái", "Lý do",
        ])
        self.time_chart = ComparisonChart()
        self.size_chart = ComparisonChart(size_chart=True)
        for widget, title in (
            (self.summary, "Tổng hợp"), (self.details, "Từng lượt"),
            (self.time_chart, "Thời gian"), (self.size_chart, "Dung lượng"),
        ):
            self.tabs.addTab(widget, title)
        self.layout.addWidget(self.tabs, 1)
        note = QLabel("Thời gian SHA-256 được đo sau giải nén. Chi phí mã hóa gồm cả mã hóa tên tệp.")
        note.setWordWrap(True)
        self.layout.addWidget(note)

        recommendation = QHBoxLayout()
        recommendation.addWidget(QLabel("Giới hạn gói"))
        self.limit = QDoubleSpinBox()
        self.limit.setDecimals(3)
        self.limit.setRange(0, 1_000_000)
        self.limit.setValue(20)
        self.limit.setSuffix(" MiB")
        self.limit.valueChanged.connect(self.recommend)
        recommendation.addWidget(self.limit)
        self.apply_button = action(recommendation, "Dùng cấu hình này", self.apply)
        recommendation.addStretch(1)
        self.layout.addLayout(recommendation)
        self.recommendation = QLabel()
        self.recommendation.setWordWrap(True)
        self.layout.addWidget(self.recommendation)
        self.clear_results()

    def pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn tệp mẫu")
        if path:
            self.set_source(Path(path))

    def pick_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục mẫu")
        if path:
            self.set_source(Path(path))

    def set_source(self, source):
        self.source = source
        self.source_label.setText(str(source))
        self.source_label.setToolTip(str(source))
        self.window.update_nav_subtitles()
        self.clear_results()

    def clear_results(self):
        self.trials = []
        if self.source is not None:
            self.status.setText("Sẵn sàng đo trên bộ mẫu đã chọn.")
        self.render_results()

    def run(self):
        if self.window.busy or self.source is None:
            return
        password = self.window.ask_password("Mật khẩu cho lượt đo AES-256", self.source.name, repeat=True)
        if password:
            source, pairs = self.source, self.pairs.value()
            self.clear_results()
            self.start(lambda progress: benchmark(source, pairs, password, progress), self.complete)

    def complete(self, trials):
        self.trials = trials
        failures = sum(row.status != "Đạt" for row in trials)
        self.status.setText(f"Đã đo {len(trials)} lượt · {failures} lỗi. Cặp hợp lệ phải đạt cả hai lượt.")
        self.render_results()

    def render_results(self):
        self.summaries = {mode: summarize(self.trials, mode) for mode in COMPRESSION}
        rows = []
        for mode, results in self.summaries.items():
            pairs = f"{results['pairs']}/{self.pairs.value()}"
            if not results["pairs"]:
                rows.append((COMPRESSION[mode], pairs, UNAVAILABLE, "", "", "", "", "", ""))
                continue
            for field, phase in results["phases"].items():
                rows.append((
                    COMPRESSION[mode], pairs, PHASES[field],
                    *(number(value, " s", 6) for value in phase["averages"]),
                    *(number(value) for value in phase["throughput"]),
                    number(phase["delta_stdev"], " s", 6), number(phase["overhead"], " %"),
                ))
            rows.append((
                COMPRESSION[mode], pairs, "Dung lượng TB",
                *(number(value, " byte", 1) for value in results["package_bytes"]), "", "", "", "",
            ))
            rows.append((
                COMPRESSION[mode], pairs, "Tiết kiệm",
                *(number(value, " %") for value in results["savings"]), "", "", "", "",
            ))
        fill_table(self.summary, rows)
        fill_table(self.details, [
            (
                row.pair, row.configuration, row.order,
                *(number(getattr(row, field), places=6) for field in PHASES),
                row.source_bytes, number(row.package_bytes, places=0),
                f"{row.matched}/{row.checked}" if row.checked is not None else "—",
                row.sha256, row.status, row.reason,
            )
            for row in self.trials
        ])
        self.time_chart.set_summaries(self.summaries)
        self.size_chart.set_summaries(self.summaries)
        self.csv_button.setEnabled(bool(self.trials))
        self.run_button.setEnabled(self.source is not None)
        self.recommend()

    def recommend(self):
        choice = recommend_mode(self.trials, self.limit.value() * MIB)
        self.recommended = None
        if choice is not None:
            self.recommended, seconds, largest, count = choice
            self.recommendation.setText(
                f"Đề xuất {COMPRESSION[self.recommended]} · tạo trung bình {seconds:.6f} s · "
                f"gói AES lớn nhất {largest:,} byte · {count} lượt AES hợp lệ."
            )
        else:
            self.recommendation.setText(
                "Không có cấu hình AES-256 đã đo hợp lệ nằm trong giới hạn."
                if self.trials else "Chạy so sánh để nhận đề xuất."
            )
        self.apply_button.setEnabled(self.recommended is not None)

    def apply(self):
        if self.recommended is not None and not self.window.busy:
            page = self.window.pages["create"]
            page.custom_destination = False
            page.compression.setCurrentIndex(page.compression.findData(self.recommended))
            page.set_source(self.source)
            self.window.navigate("create")
            self.window.choose_recommended_destination(page)

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Xuất từng lượt đo", "SafePack-so-sanh.csv", "CSV (*.csv)")
        if path:
            try:
                target = Path(path)
                if target.suffix.lower() != ".csv":
                    target = target.with_name(target.name + ".csv")
                export_trials(target, self.trials)
            except (AppError, OSError) as error:
                QMessageBox.warning(self, "Không thể xuất CSV", str(error))
            else:
                self.status.setText(f"Đã xuất {len(self.trials)} lượt vào {target}.")


class ExplorePage(TaskPage):
    def __init__(self, window):
        super().__init__(window, "restore", "Khám phá và khôi phục")
        self.manifest = None
        self.password = ""
        self.destination = None
        self.diff = []
        self.status.setText("Chọn gói .7z và nhập mật khẩu để xem danh sách tệp.")
        controls = QHBoxLayout()
        self.open_button = action(controls, "Mở gói .7z", self.pick_file)
        self.open_button.setObjectName("primary")
        self.unlock_button = action(controls, "Mở khóa", self.unlock)
        self.check_button = action(controls, "Kiểm tra gói", self.check)
        self.compare_button = action(controls, "So sánh thư mục", self.compare)
        controls.addStretch(1)
        self.layout.addLayout(controls)
        self.source_label = QLabel("Chưa chọn gói")
        self.source_label.setTextFormat(Qt.TextFormat.PlainText)
        self.source_label.setWordWrap(True)
        self.layout.addWidget(self.source_label)

        self.tabs = QTabWidget()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Tệp / thư mục", "Kích thước (byte)"])
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.itemSelectionChanged.connect(self.update_actions)
        self.tabs.addTab(self.tree, "Nội dung gói")

        diff_widget = QWidget()
        diff_layout = QVBoxLayout(diff_widget)
        self.diff_summary = QLabel("Chưa so sánh thư mục.")
        self.diff_summary.setWordWrap(True)
        diff_layout.addWidget(self.diff_summary)
        self.filter = QComboBox()
        self.filter.addItems(("Tất cả", *DIFF_GROUPS))
        self.filter.currentTextChanged.connect(self.render_diff)
        diff_layout.addWidget(self.filter, 0, Qt.AlignmentFlag.AlignLeft)
        self.diff_table = table(["Đường dẫn tương đối", "Nhóm"], stretch_last=False)
        self.diff_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        diff_layout.addWidget(self.diff_table)
        self.tabs.addTab(diff_widget, "Khác biệt với thư mục")
        self.layout.addWidget(self.tabs, 1)

        restore = QHBoxLayout()
        self.restore_all = action(restore, "Khôi phục toàn bộ", lambda: self.restore(False))
        self.restore_selected = action(restore, "Khôi phục tệp đã chọn", lambda: self.restore(True))
        self.open_output = action(restore, "Mở thư mục kết quả", self.open_restored)
        self.open_output.hide()
        restore.addStretch(1)
        self.layout.addLayout(restore)
        self.update_actions()

    def update_actions(self):
        self.unlock_button.setEnabled(self.source is not None and self.manifest is None)
        ready = self.manifest is not None
        for button in (self.check_button, self.compare_button, self.restore_all):
            button.setEnabled(ready)
        self.restore_selected.setEnabled(ready and bool(self.selected_files()))

    def pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn gói .7z", filter="Gói 7-Zip (*.7z)")
        if path:
            self.set_source(Path(path))
            self.unlock()

    def set_source(self, source):
        self.source = source
        self.source_label.setText(str(source))
        self.password = ""
        self.manifest = None
        self.destination = None
        self.diff = []
        self.diff_summary.setText("Chưa so sánh thư mục.")
        self.render_diff()
        self.tree.clear()
        self.open_output.hide()
        self.status.setText("Nhập mật khẩu để mở gói.")
        self.tabs.setCurrentIndex(0)
        self.window.update_nav_subtitles()
        self.update_actions()

    def set_destination(self, destination, *, custom=False):
        self.destination = destination

    def unlock(self):
        if self.window.busy or self.source is None:
            return
        password = self.window.ask_password("Mở gói SafePack", self.source.name)
        if password:
            source = self.source
            self.start(lambda progress: inspect_package(source, password, progress),
                       lambda manifest: self.show_manifest(manifest, password))

    def show_manifest(self, manifest, password):
        self.password, self.manifest = password, manifest
        items = {}
        self.tree.clear()
        entries = [(name, None) for name in manifest["directories"]]
        entries.extend((row["path"], row["size"]) for row in manifest["files"])
        for name, size in sorted(entries):
            parent, _, label = name.rpartition("/")
            item = QTreeWidgetItem(items.get(parent, self.tree), [label, f"{size:,}" if size is not None else ""])
            item.setToolTip(0, name)
            if size is not None:
                item.setData(0, Qt.ItemDataRole.UserRole, name)
            else:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            items[name] = item
            if not parent:
                item.setExpanded(True)
        self.status.setText(f"Đã đọc manifest · {len(manifest['files'])} tệp. Bấm Kiểm tra gói để đối chiếu SHA-256.")
        self.update_actions()

    def selected_files(self):
        return {
            item.data(0, Qt.ItemDataRole.UserRole) for item in self.tree.selectedItems()
            if item.data(0, Qt.ItemDataRole.UserRole) is not None
        }

    def check(self):
        source, password, manifest = self.source, self.password, self.manifest
        self.start(lambda progress: check_package(source, password, progress, opened_manifest=manifest),
                   lambda result: self.status.setText(f"Đã kiểm tra {result.count} tệp. Khớp SHA-256 {result.count}/{result.count}."))

    def compare(self):
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục hiện tại để so sánh")
        if path:
            manifest = self.manifest
            self.start(lambda progress: compare_folder(manifest, Path(path), progress), self.show_diff)

    def show_diff(self, diff):
        self.diff = diff
        counts = Counter(status for _, status in diff)
        self.diff_summary.setText(" · ".join(f"{status} {counts[status]}" for status in DIFF_GROUPS))
        self.filter.setCurrentIndex(0)
        self.render_diff()
        self.tabs.setCurrentIndex(1)
        self.status.setText("Đã so sánh theo đường dẫn tương đối và SHA-256.")

    def render_diff(self):
        group = self.filter.currentText()
        fill_table(self.diff_table, [(name, status) for name, status in self.diff if group in ("Tất cả", status)])

    def restore(self, selected):
        if self.window.busy or self.manifest is None:
            return
        selection = self.selected_files() if selected else None
        if selection == set():
            return
        folder = QFileDialog.getExistingDirectory(self, "Chọn nơi lưu thư mục khôi phục", str(self.source.parent))
        if not folder:
            return
        name, ok = QInputDialog.getText(self, "Khôi phục gói", "Tên thư mục mới", text=f"{self.source.stem} - khôi phục")
        if not ok:
            return
        name = name.strip()
        try:
            if len(path_parts(name)) != 1:
                raise AppError("Hãy nhập một tên thư mục duy nhất.")
        except AppError as error:
            self.show_error_result("Tên thư mục không hợp lệ", str(error))
            return
        source, password, manifest = self.source, self.password, self.manifest
        destination = Path(folder) / name
        scope = "tệp đã chọn" if selected else "tệp trong toàn bộ gói"
        self.start(
            lambda progress: restore_package(
                source, destination, password, progress, selection=selection, opened_manifest=manifest
            ),
            lambda result: self.show_restore_result(result, scope),
        )

    def show_restore_result(self, result, scope):
        self.destination = result.path
        self.status.setText(f"Đã khôi phục {result.count} {scope} · SHA-256 {result.count}/{result.count} · {result.path}")
        self.open_output.show()

    def show_success_result(self, result):
        if self.finish is None:
            self.show_restore_result(result, "tệp trong toàn bộ gói")
        else:
            super().show_success_result(result)

    def open_restored(self):
        if self.destination is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.destination)))
