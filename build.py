#!/usr/bin/env python3
"""Build a one-file Sound Pack Maker executable for the current OS."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "src" / "soundpack_maker.py"
NAME = "SoundPackMaker"


def main() -> int:
    deno_name = "deno.exe" if os.name == "nt" else "deno"
    deno = shutil.which("deno")
    if not deno:
        print(
            "Deno was not found. Install Deno 2.3+ and ensure it is on PATH, "
            "then run this build again.",
            file=sys.stderr,
        )
        return 2

    delimiter = os.pathsep
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        NAME,
        "--collect-all",
        "yt_dlp",
        "--collect-all",
        "yt_dlp_ejs",
        "--collect-all",
        "imageio_ffmpeg",
        "--add-binary",
        f"{deno}{delimiter}.",
        str(SOURCE),
    ]

    subprocess.run(command, cwd=ROOT, check=True)
    extension = ".exe" if os.name == "nt" else ""
    artifact = ROOT / "dist" / f"{NAME}{extension}"
    print(f"\nBuild complete: {artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
