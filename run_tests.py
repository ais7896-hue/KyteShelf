"""
KyteShelf - Automated Test Runner
一鍵自動化測試執行器，支援 Headless 離屏渲染、測試探索、彩色輸出與 CI 整合
"""
import os
import sys
import time
import unittest
from pathlib import Path

# 強制設定 Qt 離屏渲染以支援 Headless 測試環境 (GitHub Actions / CI)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTHONIOENCODING"] = "utf-8"

# 確保輸出支援 UTF-8，防止英文環境 (cp1252/cp437) 出現 UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 將專案根目錄加入路徑
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tests.test_helpers import get_qapp

# ANSI 顏色定義
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def run_all_tests():
    # 初始化 Headless QApplication
    get_qapp()

    print(f"\n{CYAN}{BOLD}======================================================{RESET}")
    print(f"{CYAN}{BOLD}        KyteShelf Automated Test Suite Runner         {RESET}")
    print(f"{CYAN}{BOLD}======================================================{RESET}\n")

    test_loader = unittest.TestLoader()
    test_dir = ROOT_DIR / "tests"
    
    start_time = time.time()
    suite = test_loader.discover(start_dir=str(test_dir), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    elapsed = time.time() - start_time

    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped)
    passed = total - failures - errors - skipped

    print(f"\n{BOLD}------------------------------------------------------{RESET}")
    print(f"{BOLD}測試摘要報告 (Test Summary):{RESET}")
    print(f"  總測試數 (Total)   : {total}")
    print(f"  {GREEN}通過數   (Passed)  : {passed}{RESET}")
    if failures > 0:
        print(f"  {RED}失敗數   (Failures): {failures}{RESET}")
    if errors > 0:
        print(f"  {RED}錯誤數   (Errors)  : {errors}{RESET}")
    if skipped > 0:
        print(f"  {YELLOW}略過數   (Skipped) : {skipped}{RESET}")
    print(f"  執行耗時 (Elapsed) : {elapsed:.3f} 秒")
    print(f"{BOLD}------------------------------------------------------{RESET}\n")

    if not result.wasSuccessful():
        print(f"{RED}{BOLD}[FAIL] 自動測試未通過，請修復上述錯誤！{RESET}\n")
        return 1
    else:
        print(f"{GREEN}{BOLD}[SUCCESS] 所有自動化測試順利通過！{RESET}\n")
        return 0

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
