import subprocess
import sys
from pathlib import Path


def test_startup_entrypoints_import_from_the_backend_root() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import bootstrap; import main"],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
