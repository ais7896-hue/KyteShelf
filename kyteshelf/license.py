import os
import sys
import json
import base64
import hmac
import hashlib
import urllib.request
import urllib.error
from pathlib import Path
from typing import Tuple, Optional
from PySide6.QtCore import QObject, Signal

# 預設簽名密鑰 (需與 Cloudflare Worker 的 JWT_SECRET 相同)
DEFAULT_JWT_SECRET = "KyteShelf_Secret_2026_@KeySecure"

# 預設 Worker API 網址 (使用者可在 config.json 自訂或寫死)
DEFAULT_API_BASE_URL = "https://kyteshelf-license.ais7896.workers.dev"


def get_machine_guid() -> str:
    """取得 Windows 唯一的 MachineGuid 作為硬體指紋"""
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY
            ) as key:
                guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                if guid:
                    return str(guid).strip().lower()
        except Exception:
            pass

    # Fallback: 使用 uuid.getnode (網卡 MAC) + 電腦名稱的雜湊
    import uuid
    import platform
    raw = f"{uuid.getnode()}-{platform.node()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class LicenseManager(QObject):
    license_changed = Signal(bool)  # is_activated
    _instance = None

    @classmethod
    def get_instance(cls, config_manager=None):
        if cls._instance is None:
            cls._instance = LicenseManager(config_manager)
        elif config_manager and not cls._instance.config_manager:
            cls._instance.config_manager = config_manager
        return cls._instance

    def __init__(self, config_manager=None):
        super().__init__()
        self.config_manager = config_manager
        self.machine_id = get_machine_guid()
        self.license_file = self._get_license_file_path()
        self._is_pro = False
        self._license_data = {}
        
        # 初始化時從本地快取載入並驗證
        self.verify_local_license()

    def _get_license_file_path(self) -> Path:
        appdata = Path(os.environ.get("APPDATA", Path.home())) / "KyteShelf"
        appdata.mkdir(parents=True, exist_ok=True)
        return appdata / "license.dat"

    def get_api_base_url(self) -> str:
        if self.config_manager:
            cfg = getattr(self.config_manager, "config", {})
            return cfg.get("license_api_url", DEFAULT_API_BASE_URL).rstrip("/")
        return DEFAULT_API_BASE_URL

    def is_activated(self) -> bool:
        """目前是否已啟用為永久專業版"""
        return self._is_pro

    def get_license_info(self) -> dict:
        return {
            "is_pro": self._is_pro,
            "machine_id": self.machine_id,
            "license_key": self._license_data.get("key", ""),
            "masked_key": self._mask_key(self._license_data.get("key", "")),
            "activated_at": self._license_data.get("activated_at", ""),
        }

    def _mask_key(self, key: str) -> str:
        if not key or len(key) < 10:
            return ""
        parts = key.split("-")
        if len(parts) >= 4:
            return f"{parts[0]}-****-****-{parts[-1]}"
        return f"{key[:4]}****{key[-4:]}"

    def verify_local_license(self) -> bool:
        """離線驗證本機憑證（啟動時 100% 本地運算，0 延遲）"""
        if not self.license_file.exists():
            self._is_pro = False
            self._license_data = {}
            return False

        try:
            with open(self.license_file, "r", encoding="utf-8") as f:
                content = f.read().strip()

            data = json.loads(content)
            token = data.get("token", "")
            if not token:
                self._is_pro = False
                return False

            # 驗證 Token 合法性
            payload, valid = self._verify_token(token)
            if valid and payload.get("machine_id", "").lower() == self.machine_id.lower():
                self._is_pro = True
                self._license_data = data
                return True
            else:
                # 憑證無效或被拷貝到其他電腦
                self._is_pro = False
                return False
        except Exception:
            self._is_pro = False
            return False

    def activate_online(self, key: str) -> Tuple[bool, str]:
        """連線至 Cloudflare Worker 啟用序號"""
        clean_key = key.strip().upper()
        if not clean_key:
            return False, "請輸入授權序號"

        api_url = f"{self.get_api_base_url()}/api/activate"
        payload = {
            "key": clean_key,
            "machine_id": self.machine_id,
            "machine_name": os.environ.get("COMPUTERNAME", "Windows PC")
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                api_url,
                data=req_data,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "User-Agent": "KyteShelf-Client/1.3.0 (Windows NT 10.0; Win64; x64)"
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=8) as response:
                res_body = response.read().decode("utf-8")
                res_json = json.loads(res_body)

                if res_json.get("success"):
                    token = res_json.get("token")
                    # 保存至本機
                    save_data = {
                        "key": clean_key,
                        "token": token,
                        "activated_at": str(payload.get("machine_name")),
                        "devices_used": res_json.get("devices_used", 1),
                        "max_devices": res_json.get("max_devices", 2)
                    }
                    with open(self.license_file, "w", encoding="utf-8") as f:
                        json.dump(save_data, f, indent=2, ensure_ascii=False)

                    self._is_pro = True
                    self._license_data = save_data
                    self.license_changed.emit(True)
                    return True, "🎉 授權成功！已為此電腦開通 KyteShelf 專業版。"
                else:
                    return False, res_json.get("message", "啟用失敗")

        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8")
                err_json = json.loads(err_body)
                return False, err_json.get("message", f"HTTP 錯誤: {e.code}")
            except Exception:
                return False, f"伺服器回應錯誤: {e.code}"
        except urllib.error.URLError as e:
            return False, f"網路連線失敗，請檢查網際網路連線: {e.reason}"
        except Exception as e:
            return False, f"啟用異常: {str(e)}"

    def deactivate_online(self) -> Tuple[bool, str]:
        """解除當前設備綁定（更換電腦時使用）"""
        current_key = self._license_data.get("key")
        if not current_key:
            return False, "尚未綁定任何序號"

        api_url = f"{self.get_api_base_url()}/api/deactivate"
        payload = {
            "key": current_key,
            "machine_id": self.machine_id
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                api_url,
                data=req_data,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "User-Agent": "KyteShelf-Client/1.3.0 (Windows NT 10.0; Win64; x64)"
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=8) as response:
                res_body = response.read().decode("utf-8")
                res_json = json.loads(res_body)

                # 不管遠端回傳結果如何，本機都清除憑證
                if self.license_file.exists():
                    try:
                        self.license_file.unlink()
                    except Exception:
                        pass

                self._is_pro = False
                self._license_data = {}
                self.license_changed.emit(False)
                return True, "已成功解除此電腦綁定，名額已釋放！"

        except Exception as e:
            # 即使連線有問題，亦允許使用者清除本機快取
            if self.license_file.exists():
                try:
                    self.license_file.unlink()
                except Exception:
                    pass
            self._is_pro = False
            self._license_data = {}
            self.license_changed.emit(False)
            return True, f"本機授權已清除（遠端提示: {e}）"

    def _verify_token(self, token: str) -> Tuple[dict, bool]:
        """驗證簽名 Token"""
        try:
            parts = token.split(".")
            if len(parts) != 2:
                return {}, False

            payload_b64, signature_b64 = parts

            # 解碼 Payload
            payload_str = base64.b64decode(payload_b64).decode("utf-8")
            payload = json.loads(payload_str)

            # 重新計算 HMAC-SHA256
            secret = DEFAULT_JWT_SECRET.encode("utf-8")
            expected_sig = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).digest()
            expected_sig_b64 = base64.b64encode(expected_sig).decode("utf-8").replace("+", "-").replace("/", "_").rstrip("=")

            # 比對簽名
            if hmac.compare_digest(signature_b64, expected_sig_b64):
                return payload, True
            return {}, False
        except Exception:
            return {}, False
