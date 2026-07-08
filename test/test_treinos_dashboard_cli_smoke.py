"""Smoke test: generate_report exposes the Treinos dashboard JSON mode."""

import os
import subprocess
import sys


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_generate_report_help_lists_treinos_dashboard_flag():
    out = subprocess.run(
        [sys.executable, "scripts/generate_report.py", "--help"],
        cwd=REPO, capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr
    assert "--treinos-dashboard" in out.stdout
    assert "--treinos-config" in out.stdout
