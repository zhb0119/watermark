"""Install the WujiangXu/AgenticMemory eval-repo version of A-mem.

Why: the A-mem paper's LoCoMo eval uses ``find_related_memories_raw``,
which only exists in the eval repo (WujiangXu/AgenticMemory). The
agiresearch/A-mem SDK is a clean extracted version that drops it. Our
QA path needs ``_raw`` to match the paper's protocol, so we install
from the eval repo.

The eval repo isn't pip-installable out of the box (no setup.py).
This script:

  1. clones WujiangXu/AgenticMemory into a sibling directory of the
     watermark repo (configurable via --target),
  2. drops a setup.py + a thin ``agentic_memory`` shim package on top
     so ``from agentic_memory.memory_system import AgenticMemorySystem``
     keeps working,
  3. uninstalls any prior ``agentic-memory`` install,
  4. pip installs the eval repo.

Cross-platform (macOS / Linux / Windows). Run from the watermark
repo root::

    python tools/install_amem_eval/install.py
    python tools/install_amem_eval/install.py --target ../A-mem
    python tools/install_amem_eval/install.py --break-system-packages
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_URL = "https://github.com/WujiangXu/AgenticMemory.git"
SHIM_FILES = ["setup.py", "agentic_memory/__init__.py", "agentic_memory/memory_system.py"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--target",
        default="../A-mem",
        help="Where to clone the eval repo (relative to current dir). Default: ../A-mem",
    )
    parser.add_argument(
        "--break-system-packages",
        action="store_true",
        help="Pass --break-system-packages to pip (needed on macOS Homebrew Python).",
    )
    parser.add_argument(
        "--no-clone",
        action="store_true",
        help="Skip git clone (use if --target is already a clone).",
    )
    return parser.parse_args()


def run(cmd: list[str]) -> None:
    print(f"$ {' '.join(cmd)}", flush=True)
    subprocess.check_call(cmd)


def main() -> int:
    args = parse_args()
    here = Path(__file__).resolve().parent
    target = Path(args.target).resolve()

    if not args.no_clone and not target.exists():
        run(["git", "clone", REPO_URL, str(target)])
    elif not target.exists():
        print(f"ERROR: --no-clone given but {target} doesn't exist")
        return 1

    # Copy shim files into the eval repo
    for rel in SHIM_FILES:
        src = here / rel
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"  copied {rel}")

    # Uninstall any prior agentic-memory
    pip_args_uninstall = [sys.executable, "-m", "pip", "uninstall", "-y", "agentic-memory"]
    if args.break_system_packages:
        pip_args_uninstall.insert(-1, "--break-system-packages")
    try:
        run(pip_args_uninstall)
    except subprocess.CalledProcessError:
        print("  (no prior install, OK)")

    # Install the eval repo
    pip_args_install = [sys.executable, "-m", "pip", "install", str(target)]
    if args.break_system_packages:
        pip_args_install.insert(-1, "--break-system-packages")
    run(pip_args_install)

    # Verify
    print("\nVerifying...")
    verify = subprocess.run(
        [sys.executable, "-c",
         "from agentic_memory.memory_system import AgenticMemorySystem;"
         " print('AgenticMemorySystem source:', AgenticMemorySystem.__module__);"
         " print('  find_related_memories:    ', hasattr(AgenticMemorySystem, 'find_related_memories'));"
         " print('  find_related_memories_raw:', hasattr(AgenticMemorySystem, 'find_related_memories_raw'))"
        ],
        capture_output=True, text=True,
    )
    print(verify.stdout)
    if verify.returncode != 0:
        print(verify.stderr, file=sys.stderr)
        return 1

    print("✅ Install OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
