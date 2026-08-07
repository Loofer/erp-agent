import subprocess
import sys
from pathlib import Path


def test_startup_entrypoints_import_from_the_backend_root() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    repository_root = backend_root.parent
    command = (
        "import sys; "
        f"sys.path.insert(0, {str(repository_root)!r}); "
        "import bootstrap; import main"
    )
    result = subprocess.run(
        [sys.executable, "-c", command],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
