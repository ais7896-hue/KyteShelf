import os
import sys
import time
import struct
from pathlib import Path
from typing import List

# 支援 Windows 平台的 COM 與剪貼簿虛擬檔案提取
IS_WIN = sys.platform == "win32"

if IS_WIN:
    try:
        import ctypes
        import pythoncom
        import win32com.client
    except ImportError:
        pass


def is_outlook_mime_data(mime) -> bool:
    """判斷 QMimeData 是否包含 Outlook 或 Windows 虛擬檔案描述元格式（且非本機實體檔案）"""
    if not mime:
        return False
    try:
        # 若已包含本機實體檔案路徑 (CF_HDROP)，代表是一般檔案總管拖曳或複製，絕非虛擬檔案
        if mime.hasUrls() and any(u.isLocalFile() for u in mime.urls()):
            return False
        formats = [f.lower() for f in mime.formats()]
        for fmt in formats:
            if "filegroupdescriptor" in fmt or "filecontents" in fmt or "renprivate" in fmt:
                return True
    except Exception:
        pass
    return False


def get_unique_temp_filepath(directory: Path, original_filename: str) -> Path:
    """確保檔案名稱在目錄中不重複，若已存在則自動附加序號"""
    clean_name = os.path.basename(original_filename.strip())
    # 清理 Windows 不允許的檔案名稱字元
    for char in '<>:"/\\|?*':
        clean_name = clean_name.replace(char, "_")
    if not clean_name:
        clean_name = f"attachment_{int(time.time() * 1000)}.dat"

    dest = directory / clean_name
    if not dest.exists():
        return dest

    stem = dest.stem
    suffix = dest.suffix
    counter = 1
    while True:
        candidate = directory / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def extract_attachments_from_outlook_com(target_dir: Path) -> List[str]:
    """
    透過 Windows COM 介面自動提取 Outlook 當前被選取的附件（支援 Outlook 2010、2013、2016、2019、365）。
    支援 ActiveInspector（獨立開啟之郵件視窗）與 ActiveExplorer（主收件匣視窗之閱讀窗格）。
    """
    if not IS_WIN:
        return []

    saved_files: List[str] = []
    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
    except Exception:
        return []

    # 1. 檢查 ActiveInspector（獨立開啟的郵件視窗）
    try:
        inspector = outlook.ActiveInspector()
        if inspector:
            att_sel = getattr(inspector, "AttachmentSelection", None)
            if att_sel and att_sel.Count > 0:
                for i in range(1, att_sel.Count + 1):
                    att = att_sel.Item(i)
                    filename = getattr(att, "FileName", "")
                    if filename:
                        save_path = get_unique_temp_filepath(target_dir, filename)
                        att.SaveAsFile(str(save_path))
                        if save_path.exists():
                            saved_files.append(str(save_path))
                if saved_files:
                    return saved_files
    except Exception:
        pass

    # 2. 檢查 ActiveExplorer（主介面閱讀窗格）
    try:
        explorer = outlook.ActiveExplorer()
        if explorer:
            att_sel = getattr(explorer, "AttachmentSelection", None)
            if att_sel and att_sel.Count > 0:
                for i in range(1, att_sel.Count + 1):
                    att = att_sel.Item(i)
                    filename = getattr(att, "FileName", "")
                    if filename:
                        save_path = get_unique_temp_filepath(target_dir, filename)
                        att.SaveAsFile(str(save_path))
                        if save_path.exists():
                            saved_files.append(str(save_path))
                if saved_files:
                    return saved_files
    except Exception:
        pass

    return saved_files


def extract_virtual_files_from_mime(mime, target_dir: Path) -> List[str]:
    """
    從拖放事件的 QMimeData 直接提取 FileGroupDescriptor 與 FileContents 虛擬檔案。
    專供 dropEvent 使用，絕不讀取系統剪貼簿 (OleGetClipboard)，避免誤抓 Ctrl+C 複製的檔案。
    """
    if not mime:
        return []

    saved_files: List[str] = []
    try:
        formats = list(mime.formats())
        fgd_fmt = None
        is_unicode = True
        contents_fmt = None

        for fmt in formats:
            low = fmt.lower()
            if "filegroupdescriptorw" in low:
                fgd_fmt = fmt
                is_unicode = True
            elif "filegroupdescriptor" in low and not fgd_fmt:
                fgd_fmt = fmt
                is_unicode = False
            elif "filecontents" in low and not contents_fmt:
                contents_fmt = fmt

        if not fgd_fmt or not contents_fmt:
            return []

        raw_qba = mime.data(fgd_fmt)
        data = bytes(raw_qba) if raw_qba else b""
        if len(data) < 4:
            return []

        num_files = struct.unpack_from("<I", data, 0)[0]
        fd_size = 592 if is_unicode else 332

        content_qba = mime.data(contents_fmt)
        content_bytes = bytes(content_qba) if content_qba else b""
        if not content_bytes:
            return []

        if num_files >= 1 and len(data) >= 4 + fd_size:
            fd_bytes = data[4 : 4 + fd_size]
            if is_unicode:
                name_raw = fd_bytes[72:592]
                filename = name_raw.decode("utf-16le", errors="ignore").split("\x00", 1)[0]
            else:
                name_raw = fd_bytes[72:332]
                filename = name_raw.decode("mbcs", errors="ignore").split("\x00", 1)[0]

            filename = os.path.basename(filename.strip())
            if not filename:
                filename = "dropped_attachment.dat"

            dest_path = get_unique_temp_filepath(target_dir, filename)
            with open(dest_path, "wb") as f:
                f.write(content_bytes)
            saved_files.append(str(dest_path))
    except Exception:
        pass

    return saved_files


def extract_virtual_files_from_clipboard(target_dir: Path) -> List[str]:
    """
    從 Windows 剪貼簿 OLE IDataObject 提取 FileGroupDescriptor 與 FileContents 虛擬二進位資料。
    適用於使用者在 Outlook 或其他程式中按 Ctrl+C 複製附件後於置物架 Ctrl+V 貼上的場景。
    """
    if not IS_WIN:
        return []

    saved_files: List[str] = []
    try:
        import ctypes
        import pythoncom

        try:
            pythoncom.CoInitialize()
        except Exception:
            pass

        pData = pythoncom.OleGetClipboard()
    except Exception:
        return []

    try:
        user32 = ctypes.windll.user32
        cf_hdrop = 15  # CF_HDROP
        cf_fgd_w = user32.RegisterClipboardFormatW("FileGroupDescriptorW")
        cf_fgd_a = user32.RegisterClipboardFormatW("FileGroupDescriptor")
        cf_contents = user32.RegisterClipboardFormatW("FileContents")

        fgd_format = None
        is_unicode = True
        for fmt_info in pData.EnumFormatEtc(1):
            cf = fmt_info[0]
            # 若剪貼簿內已有實體檔案 CF_HDROP，代表是一般檔案總管 Ctrl+C，不應當作虛擬檔案提取
            if cf == cf_hdrop:
                return []
            if cf == cf_fgd_w:
                fgd_format = cf
                is_unicode = True
            elif cf == cf_fgd_a and not fgd_format:
                fgd_format = cf
                is_unicode = False

        if not fgd_format:
            return []

        # 讀取 FileGroupDescriptor 結構
        med = pData.GetData((fgd_format, None, 1, -1, 1))  # TYMED_HGLOBAL = 1
        data = med.data
        if not data or len(data) < 4:
            return []

        num_files = struct.unpack_from("<I", data, 0)[0]
        fd_size = 592 if is_unicode else 332

        for i in range(num_files):
            offset = 4 + i * fd_size
            if offset + fd_size > len(data):
                break
            fd_bytes = data[offset : offset + fd_size]
            if is_unicode:
                name_raw = fd_bytes[72:592]
                filename = name_raw.decode("utf-16le", errors="ignore").split("\x00", 1)[0]
            else:
                name_raw = fd_bytes[72:332]
                filename = name_raw.decode("mbcs", errors="ignore").split("\x00", 1)[0]

            filename = os.path.basename(filename.strip())
            if not filename:
                filename = f"clipboard_attachment_{i+1}.dat"

            dest_path = get_unique_temp_filepath(target_dir, filename)

            # 透過 IDataObject 讀取第 i 個檔案的 FileContents (依序嘗試 TYMED_ISTREAM 與 TYMED_HGLOBAL)
            try:
                content_med = None
                try:
                    content_med = pData.GetData((cf_contents, None, 1, i, 4))  # TYMED_ISTREAM = 4
                except Exception:
                    content_med = None

                if content_med is None:
                    try:
                        content_med = pData.GetData((cf_contents, None, 1, i, 1))  # TYMED_HGLOBAL = 1
                    except Exception:
                        content_med = None

                if content_med:
                    if content_med.tymed == 1:  # TYMED_HGLOBAL
                        with open(dest_path, "wb") as f:
                            f.write(content_med.data)
                        saved_files.append(str(dest_path))
                    elif content_med.tymed == 4:  # TYMED_ISTREAM
                        stream = content_med.data
                        with open(dest_path, "wb") as f:
                            while True:
                                chunk = stream.Read(65536)
                                if not chunk:
                                    break
                                f.write(chunk)
                        saved_files.append(str(dest_path))
            except Exception:
                pass

    except Exception:
        pass

    return saved_files
