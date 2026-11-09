"""
C4 & Architecture Diagram Renderer
===================================

Renders every .puml file in this directory to PNG (or SVG) using one of
three backends:

    1. Kroki API (default) — Free hosted service, no install needed
    2. Local plantuml.jar  — Fully offline, requires Java 11+
    3. Docker              — Uses plantuml/plantuml image, no Java needed

Usage:
    python docs/architecture/render_diagrams.py              # Kroki (default)
    python docs/architecture/render_diagrams.py --local      # Local plantuml.jar
    python docs/architecture/render_diagrams.py --docker     # Docker
    python docs/architecture/render_diagrams.py --format svg # SVG output

Requirements:
    Kroki mode  : requests (already in requirements.txt), internet access
    Local mode  : Java 11+ and plantuml.jar (set PLANTUML_JAR or place beside script)
    Docker mode : Docker daemon running

Security Note:
    The default Kroki mode sends diagram source to a public third-party
    service. The .puml files contain no credentials, but if you later add
    internal hostnames or client names, switch to --local or --docker.

Version: 2.0.0
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal

import requests

HERE = Path(__file__).resolve().parent
KROKI_BASE = "https://kroki.io"
MAX_RETRIES = 3
RETRY_DELAY = 2.0

Format = Literal["png", "svg"]
Mode = Literal["kroki", "local", "docker"]


# =============================================================================
# DISCOVERY
# =============================================================================

def discover_diagrams() -> list[Path]:
    """Find all PlantUML source files, sorted for deterministic output."""
    files = sorted(HERE.glob("*.puml"))
    if not files:
        print(f"No .puml files found in {HERE}", file=sys.stderr)
    return files


def output_path(source: Path, fmt: Format) -> Path:
    """Determine the output path for a rendered diagram."""
    out_dir = HERE / fmt
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{source.stem}.{fmt}"


# =============================================================================
# BACKEND: KROKI (Hosted PlantUML Rendering)
# =============================================================================

def render_kroki(source: Path, fmt: Format) -> Path:
    """
    Render via the Kroki HTTP API.

    Sends diagram source to https://kroki.io for rendering.
    Includes retry logic for transient network failures.
    """
    url = f"{KROKI_BASE}/plantuml/{fmt}"
    payload = source.read_text(encoding="utf-8")
    dest = output_path(source, fmt)

    last_error: str | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(
                url,
                data=payload.encode("utf-8"),
                headers={"Content-Type": "text/plain; charset=utf-8"},
                timeout=60,
            )
            if response.status_code == 200:
                dest.write_bytes(response.content)
                return dest

            last_error = f"HTTP {response.status_code}: {response.text[:400]}"
            print(f"  attempt {attempt}/{MAX_RETRIES} failed — {last_error}")

        except requests.RequestException as exc:
            last_error = str(exc)
            print(f"  attempt {attempt}/{MAX_RETRIES} failed — {last_error}")

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY * attempt)

    raise RuntimeError(f"Kroki rendering failed for {source.name}: {last_error}")


# =============================================================================
# BACKEND: LOCAL PLANTUML.JAR
# =============================================================================

def render_local(source: Path, fmt: Format) -> Path:
    """
    Render using a local plantuml.jar. Fully offline.

    Requires:
        - Java 11+ on PATH
        - plantuml.jar at $PLANTUML_JAR or in this directory
    """
    if shutil.which("java") is None:
        raise RuntimeError(
            "Java not found on PATH. Install Java 11+ or use --docker."
        )

    jar = os.getenv("PLANTUML_JAR") or str(HERE / "plantuml.jar")
    if not Path(jar).is_file():
        raise RuntimeError(
            f"plantuml.jar not found at {jar}.\n"
            "Download from https://plantuml.com/download and set PLANTUML_JAR."
        )

    dest = output_path(source, fmt)
    flag = "-tpng" if fmt == "png" else "-tsvg"

    result = subprocess.run(
        [
            "java", "-jar", jar, flag,
            "-charset", "UTF-8",
            "-o", str(dest.parent),
            str(source),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"PlantUML failed:\n{result.stderr}")

    return dest


# =============================================================================
# BACKEND: DOCKER
# =============================================================================

def render_docker(source: Path, fmt: Format) -> Path:
    """
    Render using the plantuml/plantuml Docker image.
    No Java install needed — just Docker daemon.
    """
    if shutil.which("docker") is None:
        raise RuntimeError("Docker not found on PATH.")

    dest = output_path(source, fmt)
    flag = "-tpng" if fmt == "png" else "-tsvg"

    cmd = [
        "docker", "run", "--rm",
        "-v", f"{HERE}:/work",
        "-w", "/work",
        "plantuml/plantuml:latest",
        flag,
        "-charset", "UTF-8",
        "-o", fmt,
        source.name,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Docker PlantUML failed:\n{result.stderr}")

    return dest


# =============================================================================
# ENTRY POINT
# =============================================================================

RENDERERS = {
    "kroki": render_kroki,
    "local": render_local,
    "docker": render_docker,
}


def main() -> int:
    """Main entry point — parse args and render all diagrams."""
    parser = argparse.ArgumentParser(
        description="Render C4 and architecture diagrams to PNG/SVG.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python render_diagrams.py              # Use Kroki API (default)
  python render_diagrams.py --local      # Use local plantuml.jar
  python render_diagrams.py --docker     # Use Docker
  python render_diagrams.py --format svg # Output SVG instead of PNG
        """,
    )
    backend = parser.add_mutually_exclusive_group()
    backend.add_argument(
        "--local", action="store_true",
        help="Use local plantuml.jar (requires Java 11+)"
    )
    backend.add_argument(
        "--docker", action="store_true",
        help="Use Docker plantuml image (requires Docker)"
    )
    parser.add_argument(
        "--format", choices=["png", "svg"], default="png",
        help="Output format (default: png)"
    )
    args = parser.parse_args()

    mode: Mode = "local" if args.local else "docker" if args.docker else "kroki"
    renderer = RENDERERS[mode]

    diagrams = discover_diagrams()
    if not diagrams:
        return 1

    print(f"Rendering {len(diagrams)} diagram(s) via '{mode}' → {args.format.upper()}\n")
    print(f"Source directory: {HERE}")
    print(f"Output directory: {HERE / args.format}\n")
    print("=" * 60)

    failures: list[tuple[str, str]] = []
    for source in diagrams:
        print(f"→ {source.name}")
        try:
            dest = renderer(source, args.format)
            size_kb = dest.stat().st_size / 1024
            print(f"  ✓ {dest.relative_to(HERE.parent.parent)} ({size_kb:.1f} KB)\n")
        except Exception as exc:
            print(f"  ✗ {exc}\n")
            failures.append((source.name, str(exc)))

    print("=" * 60)
    print(f"Succeeded: {len(diagrams) - len(failures)} / {len(diagrams)}")

    if failures:
        print("\nFailures:")
        for name, err in failures:
            print(f"  - {name}: {err.splitlines()[0]}")
        return 1

    print(f"\n✅ All diagrams rendered successfully!")
    print(f"📁 Output: {HERE / args.format}")
    return 0


if __name__ == "__main__":
    sys.exit(main())