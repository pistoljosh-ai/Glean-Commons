#!/usr/bin/env python3
"""Render the Glean Commons 3D explainer using local Blender and FFmpeg."""

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from score import write_score

CELL = Path(__file__).resolve().parent


def find_tool(name, requested):
    executable = shutil.which(requested or name)
    if executable is None and name == "blender" and requested is None:
        executable = shutil.which("/Applications/Blender.app/Contents/MacOS/Blender")
    if executable is None:
        raise ValueError(f"Install {name} or pass its path with --{name}.")
    return executable


def validate_storyboard(path):
    shots = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(shots, list) or len(shots) != 6:
        raise ValueError("The storyboard must have six shots.")
    for shot in shots:
        if not isinstance(shot, list) or len(shot) != 2 or any(
            not isinstance(line, str) or not line.strip() or len(line) > limit
            or not line.isprintable()
            for line, limit in zip(shot, (36, 78))
        ):
            raise ValueError("Each shot needs a title (up to 36 characters) and a caption (up to 78).")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New MP4, or a PNG with --preview.")
    parser.add_argument("--storyboard", type=Path, default=CELL / "storyboard.json")
    parser.add_argument("--blender", help="Path to the Blender executable.")
    parser.add_argument("--ffmpeg", help="Path to the FFmpeg executable.")
    parser.add_argument("--preview", action="store_true", help="Render one frame to PNG.")
    args = parser.parse_args()
    output = args.output.resolve()
    try:
        if output.suffix.lower() != (".png" if args.preview else ".mp4"):
            raise ValueError("Use a PNG for preview or an MP4 for the film.")
        if output.exists():
            raise ValueError(f"Output already exists: {output}")
        validate_storyboard(args.storyboard)
        blender = find_tool("blender", args.blender)
        ffmpeg = None if args.preview else find_tool("ffmpeg", args.ffmpeg)
        with TemporaryDirectory(prefix="glean-3d-", dir=output.parent) as directory:
            temp = Path(directory)
            subprocess.run([
                blender, "-b", "--factory-startup", "--python-exit-code", "1",
                "--python", str(CELL / "scene.py"), "--", str(args.storyboard.resolve()),
                str(temp), "preview" if args.preview else "film",
            ], check=True)
            result = temp / "preview.png"
            if not args.preview:
                score = temp / "score.wav"
                result = temp / "film.mp4"
                write_score(score, 36)
                subprocess.run([
                    ffmpeg, "-hide_banner", "-loglevel", "error",
                    "-framerate", "16", "-start_number", "1", "-i", str(temp / "%04d.png"),
                    "-i", str(score), "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(result),
                ], check=True)
            output.hardlink_to(result)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
