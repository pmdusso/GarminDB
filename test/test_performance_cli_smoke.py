# test/test_performance_cli_smoke.py
import os
import subprocess
import sys
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DBS = os.path.expanduser("~/HealthData/DBs/garmin.db")


@pytest.mark.skipif(not os.path.exists(DBS), reason="real DBs not present")
def test_performance_cli_generates_report(tmp_path):
    out = tmp_path / "perf.md"
    result = subprocess.run(
        [sys.executable, "scripts/generate_report.py", "--performance",
         "--start", "2026-05-09", "--end", "2026-06-07", "-o", str(out)],
        cwd=REPO, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    text = out.read_text()
    assert "Resumo Executivo" in text
    assert "W/kg" in text
    assert "PRONTIDÃO" in text.upper()
