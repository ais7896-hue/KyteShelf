"""
KyteShelf - Automated Test Runner
根目錄一鍵自動化測試入口
"""
import sys
from pathlib import Path

# 將 tests/run_tests.py 加入路徑並執行
TESTS_DIR = Path(__file__).resolve().parent / "tests"
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from run_tests import main

if __name__ == "__main__":
    main()
