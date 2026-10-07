"""
KyteShelf - 通用更新檢查與自動下載升級模組
支援: GitHub Pages (version.json) CDN 優先 + GitHub Releases API 備援
"""
import os
import sys
import json
import time
import re
import tempfile
import subprocess
import urllib.request
from typing import Optional, Callable

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QTextEdit, QPushButton, QProgressBar, QMessageBox, QApplication
)

try:
    from .i18n import t
except Exception:
    def t(k, **kwargs):
        fallback = {
            "update.title": "發現新版本",
            "update.found": "🎉 發現 {app_name} 新版本：v{new_ver}",
            "update.current": "目前安裝版本：v{current_ver}",
            "update.notes": "更新摘要：",
            "update.btn_skip": "略過此版本",
            "update.btn_later": "稍後提醒",
            "update.btn_update": "立即下載並更新",
            "update.downloading": "正在下載最新安裝包...",
            "update.download_complete": "下載完成！即將啟動安裝精靈...",
            "update.download_failed": "下載失敗",
            "update.err_no_url": "未找到安裝程式下載位址，請至官網下載。",
            "update.err_download": "無法下載安裝檔：\n{err}",
            "update.err_launch": "無法啟動安裝程式：\n{err}",
            "update.latest_title": "檢查更新",
            "update.latest_msg": "目前已是最新版本 (v{ver})！",
            "update.err_conn": "連線至伺服器時發生錯誤：\n{err}"
        }
        text = fallback.get(k, k)
        return text.format(**kwargs) if kwargs else text


def parse_version(v: str) -> tuple:
    """語義化版本解析，例如 '1.4.0' -> (1, 4, 0)"""
    nums = re.findall(r"\d+", str(v))
    return tuple(int(n) for n in nums) if nums else (0,)


class CheckUpdateWorker(QThread):
    """背景非同步檢查更新線程"""
    # 訊號參數: (has_update: bool, latest_ver: str, notes: str, download_url: str)
    checked = Signal(bool, str, str, str)
    error = Signal(str)

    def __init__(self, current_ver: str, repo: str, cname_domain: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.current_ver = current_ver
        self.repo = repo                     # 例如: "ais7896-hue/KyteShelf"
        self.cname_domain = cname_domain     # 例如: "kyteshelf.aisming.com"

    def run(self):
        latest_ver = ""
        notes = ""
        download_url = ""

        # 策略 1: 優先向官網/CDN 請求 version.json (無 GitHub API 60次/hr 限流)
        if self.cname_domain:
            try:
                url = f"https://{self.cname_domain}/version.json?_t={int(time.time())}"
                req = urllib.request.Request(url, headers={"User-Agent": "KyteUpdater/1.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        latest_ver = str(data.get("version", "")).lstrip("v")
                        notes = data.get("notes", "")
                        download_url = data.get("download_url", "")
            except Exception:
                pass

        # 策略 2: Fallback 呼叫 GitHub Releases API
        if not latest_ver or not download_url:
            try:
                url = f"https://api.github.com/repos/{self.repo}/releases/latest"
                req = urllib.request.Request(url, headers={"User-Agent": "KyteUpdater/1.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    latest_ver = str(data.get("tag_name", "")).lstrip("v")
                    notes = data.get("body", "無更新日誌說明。")
                    assets = data.get("assets", [])
                    
                    # 搜尋 Inno Setup 產出的 Setup.exe
                    for asset in assets:
                        name = asset.get("name", "").lower()
                        if name.endswith(".exe") and "setup" in name:
                            download_url = asset.get("browser_download_url")
                            break
                    if not download_url and assets:
                        for asset in assets:
                            if asset.get("name", "").lower().endswith(".exe"):
                                download_url = asset.get("browser_download_url")
                                break
            except Exception as e:
                self.error.emit(f"無法檢查版本更新: {str(e)}")
                return

        # 語義化版本比對
        if latest_ver and parse_version(latest_ver) > parse_version(self.current_ver):
            self.checked.emit(True, latest_ver, notes, download_url)
        else:
            self.checked.emit(False, latest_ver or self.current_ver, "", "")


class DownloadWorker(QThread):
    """背景串流下載安裝檔線程"""
    progress = Signal(int, str)  # (百分比, 狀態文字)
    finished = Signal(str)       # 下載完成後的本地完整檔案路徑
    error = Signal(str)

    def __init__(self, download_url: str, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            filename = self.download_url.split("/")[-1].split("?")[0]
            if not filename.endswith(".exe"):
                filename = "KyteShelf_Setup.exe"
            dest_path = os.path.join(tempfile.gettempdir(), filename)

            req = urllib.request.Request(self.download_url, headers={"User-Agent": "KyteUpdater/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp, open(dest_path, "wb") as f:
                total_size = int(resp.getheader("content-length", -1))
                downloaded = 0
                chunk_size = 64 * 1024

                while not self._is_cancelled:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = int(downloaded / total_size * 100)
                        mb_text = f"{downloaded / (1024*1024):.1f} MB / {total_size / (1024*1024):.1f} MB"
                        self.progress.emit(min(pct, 100), mb_text)
                    else:
                        self.progress.emit(50, f"{downloaded / (1024*1024):.1f} MB")

            if self._is_cancelled:
                if os.path.exists(dest_path):
                    try: os.remove(dest_path)
                    except OSError: pass
                return

            self.finished.emit(dest_path)
        except Exception as e:
            self.error.emit(str(e))


class UpdateDialog(QDialog):
    """現代更新提示與下載對話框"""
    def __init__(
        self, 
        app_name: str, 
        current_ver: str, 
        new_ver: str, 
        notes: str, 
        download_url: str, 
        on_skip_cb: Optional[Callable[[str], None]] = None, 
        parent=None
    ):
        super().__init__(parent)
        self.app_name = app_name
        self.current_ver = current_ver
        self.new_ver = new_ver
        self.notes = notes
        self.download_url = download_url
        self.on_skip_cb = on_skip_cb
        self.download_worker: Optional[DownloadWorker] = None

        self.setWindowTitle(f"{app_name} - {t('update.title')}")
        self.setFixedSize(540, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(22, 22, 22, 22)

        # 頂部標題區
        title_box = QVBoxLayout()
        title_text = t("update.found", app_name=self.app_name, new_ver=self.new_ver)
        h_title = QLabel(f"<span style='font-size:16px; font-weight:bold;'>{title_text}</span>")
        curr_text = t("update.current", current_ver=self.current_ver)
        sub_title = QLabel(f"<span style='color: #888;'>{curr_text}</span>")
        title_box.addWidget(h_title)
        title_box.addWidget(sub_title)
        layout.addLayout(title_box)

        # 更新日誌內容
        lbl_notes = QLabel(f"<b>{t('update.notes')}</b>")
        layout.addWidget(lbl_notes)
        self.txt_notes = QTextEdit()
        self.txt_notes.setReadOnly(True)
        self.txt_notes.setPlainText(self.notes)
        self.txt_notes.setStyleSheet("border-radius: 6px; padding: 8px; line-height: 1.4;")
        layout.addWidget(self.txt_notes)

        # 下載進度條
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("")
        self.status_lbl.setVisible(False)
        self.status_lbl.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.status_lbl)

        # 按鈕列
        self.btn_layout = QHBoxLayout()
        self.btn_skip = QPushButton(t("update.btn_skip"))
        self.btn_skip.clicked.connect(self._on_skip)

        self.btn_later = QPushButton(t("update.btn_later"))
        self.btn_later.clicked.connect(self.reject)

        self.btn_update = QPushButton(t("update.btn_update"))
        self.btn_update.setObjectName("btn_primary")
        self.btn_update.setStyleSheet(
            "background-color: #0284c7; color: white; font-weight: bold; "
            "border-radius: 6px; padding: 6px 16px; min-height: 30px;"
        )
        self.btn_update.clicked.connect(self._start_download)

        self.btn_layout.addWidget(self.btn_skip)
        self.btn_layout.addStretch()
        self.btn_layout.addWidget(self.btn_later)
        self.btn_layout.addWidget(self.btn_update)
        layout.addLayout(self.btn_layout)

    def _on_skip(self):
        if self.on_skip_cb:
            self.on_skip_cb(self.new_ver)
        self.reject()

    def _start_download(self):
        if not self.download_url:
            QMessageBox.warning(self, t("update.error_title", default="錯誤"), t("update.err_no_url"))
            return

        self.btn_update.setEnabled(False)
        self.btn_later.setEnabled(False)
        self.btn_skip.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_lbl.setVisible(True)
        self.status_lbl.setText(t("update.downloading"))

        self.download_worker = DownloadWorker(self.download_url, self)
        self.download_worker.progress.connect(self._on_progress)
        self.download_worker.finished.connect(self._on_finished)
        self.download_worker.error.connect(self._on_error)
        self.download_worker.start()

    def _on_progress(self, pct: int, status_text: str):
        self.progress_bar.setValue(pct)
        self.status_lbl.setText(f"{t('update.downloading')} ({status_text})")

    def _on_error(self, err_msg: str):
        self.btn_update.setEnabled(True)
        self.btn_later.setEnabled(True)
        self.btn_skip.setEnabled(True)
        self.status_lbl.setText(t("update.download_failed"))
        QMessageBox.critical(self, t("update.download_failed"), t("update.err_download", err=err_msg))

    def _on_finished(self, installer_path: str):
        self.status_lbl.setText(t("update.download_complete"))
        
        # 關鍵交接：啟動安裝檔並退出主程式，釋放所有檔案鎖定
        try:
            subprocess.Popen([installer_path])
            QApplication.quit()
            sys.exit(0)
        except Exception as e:
            QMessageBox.critical(self, t("update.launch_failed_title", default="啟動失敗"), t("update.err_launch", err=str(e)))
