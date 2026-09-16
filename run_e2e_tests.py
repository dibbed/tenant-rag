"""Run E2E tests and write results to file."""
import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
os.chdir(root)
out_path = root / "e2e_test_output.txt"
try:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/e2e/test_project_e2e_complete.py", "-v", "--tb=long"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(root),
    )
    out = result.stdout + "\n\n=== STDERR ===\n" + result.stderr + f"\n\n=== EXIT CODE: {result.returncode} ==="
    out_path.write_text(out, encoding="utf-8")
    sys.exit(result.returncode)
except Exception as e:
    import traceback
    out_path.write_text(f"ERROR: {e}\n{traceback.format_exc()}", encoding="utf-8")
    sys.exit(1)
