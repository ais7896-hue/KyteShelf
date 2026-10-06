#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
KyteShelf 自動化測試主執行檔
執行方式:
    python tests/run_tests.py
    或者:
    python -m unittest discover -s tests
"""
import os
import sys
import time
import unittest
from pathlib import Path

# 強制設定 Qt 離屏渲染以支援無頭 (Headless) 測試環境
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# 確保 Windows 終端機支援 UTF-8 輸出
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_helpers import get_qapp


def main():
    # 確保 Qt Application 實例就緒
    get_qapp()

    print("=" * 65)
    print("🚀 KyteShelf 自動化單元測試啟動中...")
    print("=" * 65)

    tests_dir = Path(__file__).resolve().parent
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(tests_dir), pattern="test_*.py")

    start_time = time.time()
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    elapsed = time.time() - start_time

    print("\n" + "=" * 65)
    print(f"📊 測試總結報告:")
    print(f"   總執行測試數 : {result.testsRun}")
    print(f"   通過測試數   : {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"   失敗數 (Fail): {len(result.failures)}")
    print(f"   錯誤數 (Err) : {len(result.errors)}")
    print(f"   總耗時       : {elapsed:.3f} 秒")
    print("=" * 65)

    if not result.wasSuccessful():
        print("❌ 測試未完全通過！請檢查上述失敗項目。")
        sys.exit(1)
    else:
        print("✅ 所有重要功能自動化測試皆順利通過！")
        sys.exit(0)


if __name__ == "__main__":
    main()
