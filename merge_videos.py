"""Merge numbered episode video files in a folder into a single video.

Usage:
    python merge_videos.py "C:\\path\\to\\folder" [-o output_file]

Files are ordered by episode number ("Episode 2" comes before "Episode 10").
If ffmpeg is on PATH, files are joined losslessly into an .mp4 with the concat
demuxer. Otherwise .ts files are joined byte-for-byte, which is valid for the
MPEG-TS format and plays in VLC, MPV, and most players.
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VIDEO_EXTENSIONS = {".ts", ".mp4", ".mkv", ".mov", ".avi", ".m4v", ".webm"}
CHUNK_SIZE = 16 * 1024 * 1024
MERGED_SUFFIX = " - Merged"


def natural_key(path: Path):
    """Sort key that compares embedded numbers numerically."""
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", path.stem)]


def find_videos(folder: Path) -> list[Path]:
    files = [p for p in folder.iterdir()
             if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
             and not p.stem.endswith(MERGED_SUFFIX)]
    return sorted(files, key=natural_key)


def merge_with_ffmpeg(ffmpeg: str, files: list[Path], output: Path) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                     encoding="utf-8") as list_file:
        for f in files:
            escaped = str(f.resolve()).replace("'", r"'\''")
            list_file.write(f"file '{escaped}'\n")
        list_path = list_file.name
    command = [ffmpeg, "-hide_banner", "-loglevel", "warning", "-y",
               "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy"]
    if output.suffix.lower() in {".mp4", ".m4v", ".mov"}:
        command += ["-bsf:a", "aac_adtstoasc"]
    try:
        subprocess.run(command + [str(output)], check=True)
    finally:
        Path(list_path).unlink(missing_ok=True)


def merge_binary(files: list[Path], output: Path) -> None:
    with output.open("wb") as out:
        for i, f in enumerate(files, 1):
            print(f"  [{i}/{len(files)}] {f.name}")
            with f.open("rb") as src:
                shutil.copyfileobj(src, out, CHUNK_SIZE)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", type=Path, help="folder containing the episodes")
    parser.add_argument("-o", "--output", type=Path,
                        help="output file (default: '<folder name> - Merged' inside the folder)")
    args = parser.parse_args()

    folder = args.folder.resolve()
    if not folder.is_dir():
        print(f"Not a folder: {folder}", file=sys.stderr)
        return 1

    files = find_videos(folder)
    if not files:
        print(f"No video files found in {folder}", file=sys.stderr)
        return 1

    ffmpeg = shutil.which("ffmpeg")
    extensions = {f.suffix.lower() for f in files}
    if not ffmpeg and extensions != {".ts"}:
        print("ffmpeg is required to merge non-.ts files. "
              "Install it with: winget install Gyan.FFmpeg", file=sys.stderr)
        return 1

    default_ext = ".mp4" if ffmpeg else ".ts"
    output = args.output or folder / f"{folder.name}{MERGED_SUFFIX}{default_ext}"
    if output.resolve().parent == folder:
        files = [f for f in files if f.resolve() != output.resolve()]

    print(f"Merging {len(files)} files in this order:")
    for f in files:
        print(f"  {f.name}")

    if ffmpeg:
        print(f"\nUsing ffmpeg: {ffmpeg}")
        merge_with_ffmpeg(ffmpeg, files, output)
    else:
        print("\nffmpeg not found; joining .ts files directly")
        merge_binary(files, output)

    size_mb = output.stat().st_size / (1024 * 1024)
    print(f"\nDone: {output} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
