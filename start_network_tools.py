"""Run NETWORK-TOOLS as one Django service."""
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main():
    print("\nNETWORK-TOOLS: http://127.0.0.1:8501\n")
    subprocess.run(
        [sys.executable, "manage.py", "runserver", "127.0.0.1:8501"],
        cwd=ROOT,
        check=False,
    )


if __name__ == "__main__":
    main()
