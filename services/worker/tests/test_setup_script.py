from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="the worker installer targets Windows")
def test_setup_script_reuses_python312_environment_and_reports_device_mode():
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "setup-photo-worker.ps1"
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-Device",
            "auto",
            "-Dev",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Worker environment ready: Python 3.12" in result.stdout
    assert "requested device mode auto" in result.stdout
    assert "weights remain uninstalled" in result.stdout
