import base64
import hashlib
import hmac
import json
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.test_helpers import get_qapp
from kyteshelf.license import (
    DEFAULT_JWT_SECRET,
    FREE_MAX_FILES_PER_SHELF,
    FREE_MAX_SHELVES,
    TRIAL_DAYS,
    LicenseManager,
    get_machine_guid,
)


class TestLicenseManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        get_qapp()

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.license_file = Path(self.temp_dir.name) / "license.dat"
        self.trial_file = Path(self.temp_dir.name) / "trial.dat"

        # Reset singleton instance between tests
        LicenseManager._instance = None

    def tearDown(self):
        self.temp_dir.cleanup()
        LicenseManager._instance = None

    def _create_manager(self, config_manager=None):
        with patch.object(LicenseManager, "_get_license_file_path", return_value=self.license_file), \
             patch.object(LicenseManager, "_get_trial_file_path", return_value=self.trial_file):
            return LicenseManager(config_manager)

    def test_machine_guid_not_empty(self):
        guid = get_machine_guid()
        self.assertTrue(bool(guid))
        self.assertIsInstance(guid, str)
        self.assertGreater(len(guid), 5)

    def test_trial_initialization_on_first_run(self):
        manager = self._create_manager()

        self.assertTrue(self.trial_file.exists())
        self.assertEqual(manager.get_plan_type(), "trial")
        self.assertTrue(manager.is_unlimited())
        self.assertFalse(manager.is_activated())
        self.assertEqual(manager.get_trial_days_left(), TRIAL_DAYS)

        with open(self.trial_file, "r", encoding="utf-8") as f:
            trial_data = json.load(f)
        self.assertIn("first_run", trial_data)
        self.assertIn("sig", trial_data)
        self.assertEqual(trial_data["machine_id"], manager.machine_id)

    def test_trial_tamper_detection(self):
        manager = self._create_manager()
        self.assertTrue(manager.is_unlimited())

        # Tamper trial file with invalid signature
        with open(self.trial_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["sig"] = "tampered_fake_signature"
        with open(self.trial_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        # Reload manager
        reloaded = self._create_manager()
        self.assertFalse(reloaded.is_unlimited(), "Tampered trial should be invalid")
        self.assertEqual(reloaded.get_plan_type(), "free")
        self.assertEqual(reloaded.get_trial_days_left(), 0)

    def test_trial_clock_rollback_detection(self):
        manager = self._create_manager()

        # Simulate running in the future, then clock winding back > 120s
        with open(self.trial_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        secret = DEFAULT_JWT_SECRET.encode("utf-8")
        future_seen = time.time() + 3600  # 1 hour in future
        first_run = data["first_run"]
        sig_raw = f"{first_run:.0f}:{future_seen:.0f}:{data['machine_id']}"
        sig = hmac.new(secret, sig_raw.encode("utf-8"), hashlib.sha256).hexdigest()

        data["last_seen"] = future_seen
        data["sig"] = sig
        with open(self.trial_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        # Reload manager with current time (which is 1 hr before last_seen)
        reloaded = self._create_manager()
        self.assertFalse(reloaded.is_unlimited(), "Time rollback must invalidate trial")
        self.assertEqual(reloaded.get_plan_type(), "free")

    def test_trial_expired_after_14_days(self):
        secret = DEFAULT_JWT_SECRET.encode("utf-8")
        machine_id = get_machine_guid()
        fifteen_days_ago = time.time() - (15 * 86400)
        sig_raw = f"{fifteen_days_ago:.0f}:{fifteen_days_ago:.0f}:{machine_id}"
        sig = hmac.new(secret, sig_raw.encode("utf-8"), hashlib.sha256).hexdigest()

        trial_data = {
            "first_run": fifteen_days_ago,
            "last_seen": fifteen_days_ago,
            "machine_id": machine_id,
            "sig": sig
        }
        with open(self.trial_file, "w", encoding="utf-8") as f:
            json.dump(trial_data, f)

        manager = self._create_manager()
        self.assertFalse(manager.is_unlimited())
        self.assertEqual(manager.get_plan_type(), "free")
        self.assertEqual(manager.get_trial_days_left(), 0)

    def test_feature_restrictions_in_free_mode(self):
        # Force free mode by creating an expired trial
        fifteen_days_ago = time.time() - (15 * 86400)
        secret = DEFAULT_JWT_SECRET.encode("utf-8")
        machine_id = get_machine_guid()
        sig_raw = f"{fifteen_days_ago:.0f}:{fifteen_days_ago:.0f}:{machine_id}"
        sig = hmac.new(secret, sig_raw.encode("utf-8"), hashlib.sha256).hexdigest()
        with open(self.trial_file, "w", encoding="utf-8") as f:
            json.dump({
                "first_run": fifteen_days_ago,
                "last_seen": fifteen_days_ago,
                "machine_id": machine_id,
                "sig": sig
            }, f)

        manager = self._create_manager()
        self.assertEqual(manager.get_plan_type(), "free")

        # Test shelf creation limits
        can_create, _ = manager.can_create_shelf(current_visible_count=0)
        self.assertTrue(can_create)
        can_create_second, reason = manager.can_create_shelf(current_visible_count=FREE_MAX_SHELVES)
        self.assertFalse(can_create_second)
        self.assertIn("免費版最多", reason)

        # Test adding files limit
        allowed, _ = manager.can_add_files(current_file_count=3, incoming_count=2)
        self.assertEqual(allowed, 2)
        allowed_exceeded, warn_msg = manager.can_add_files(current_file_count=4, incoming_count=3)
        self.assertEqual(allowed_exceeded, 1)  # Only 1 slot left
        self.assertIn("上限", warn_msg)

        # Test Pro-only features
        can_zip, zip_reason = manager.can_use_zip()
        self.assertFalse(can_zip)
        self.assertIn("Pro", zip_reason)

        can_watch, watch_reason = manager.can_use_folder_watch()
        self.assertFalse(can_watch)
        self.assertIn("Pro", watch_reason)

    def test_feature_permissions_in_pro_mode(self):
        manager = self._create_manager()
        manager._is_pro = True

        self.assertTrue(manager.is_unlimited())
        self.assertEqual(manager.get_plan_type(), "pro")

        can_create, _ = manager.can_create_shelf(current_visible_count=100)
        self.assertTrue(can_create)

        allowed, _ = manager.can_add_files(current_file_count=100, incoming_count=50)
        self.assertEqual(allowed, 50)

        can_zip, _ = manager.can_use_zip()
        self.assertTrue(can_zip)

        can_watch, _ = manager.can_use_folder_watch()
        self.assertTrue(can_watch)

    def test_token_verification_and_offline_license(self):
        manager = self._create_manager()

        # Build valid token for this machine
        payload = {
            "key": "KS-TEST-1234-ABCD",
            "machine_id": manager.machine_id,
            "created_at": time.time()
        }
        payload_bytes = json.dumps(payload).encode("utf-8")
        payload_b64 = base64.b64encode(payload_bytes).decode("utf-8")

        secret = DEFAULT_JWT_SECRET.encode("utf-8")
        expected_sig = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).digest()
        sig_b64 = base64.b64encode(expected_sig).decode("utf-8").replace("+", "-").replace("/", "_").rstrip("=")
        valid_token = f"{payload_b64}.{sig_b64}"

        # Test _verify_token directly
        decoded_payload, is_valid = manager._verify_token(valid_token)
        self.assertTrue(is_valid)
        self.assertEqual(decoded_payload["key"], "KS-TEST-1234-ABCD")

        # Save to license file
        with open(self.license_file, "w", encoding="utf-8") as f:
            json.dump({
                "key": "KS-TEST-1234-ABCD",
                "token": valid_token,
                "activated_at": "TestPC"
            }, f)

        # Test verify_local_license
        verified = manager.verify_local_license()
        self.assertTrue(verified)
        self.assertTrue(manager.is_activated())
        self.assertEqual(manager.get_plan_type(), "pro")

    @patch("urllib.request.urlopen")
    def test_activate_online_success(self, mock_urlopen):
        manager = self._create_manager()

        # Mock server successful response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "success": True,
            "token": "fake.token",
            "devices_used": 1,
            "max_devices": 2
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        # Listen to license_changed signal
        signal_events = []
        manager.license_changed.connect(signal_events.append)

        success, msg = manager.activate_online("KS-TEST-KEY-0001")
        self.assertTrue(success)
        self.assertIn("授權成功", msg)
        self.assertTrue(manager.is_activated())
        self.assertEqual(signal_events, [True])
        self.assertTrue(self.license_file.exists())

    @patch("urllib.request.urlopen")
    def test_activate_online_failure_message(self, mock_urlopen):
        manager = self._create_manager()

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "success": False,
            "message": "序號不存在或已作廢"
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        success, msg = manager.activate_online("INVALID-KEY")
        self.assertFalse(success)
        self.assertIn("序號不存在", msg)
        self.assertFalse(manager.is_activated())

    def test_mask_key(self):
        manager = self._create_manager()
        masked = manager._mask_key("AAAA-BBBB-CCCC-DDDD")
        self.assertEqual(masked, "AAAA-****-****-DDDD")


if __name__ == "__main__":
    unittest.main()
