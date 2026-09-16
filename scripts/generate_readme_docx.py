#!/usr/bin/env python3
"""
Generate a DOCX from a Markdown file.

Usage:
  python scripts/generate_readme_docx.py --input docs/README_FULL.md --output docs/README_FULL.docx

Requirements:
  - pypandoc (pip install pypandoc)
  - Pandoc installed on system: https://pandoc.org/installing.html
"""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert Markdown to DOCX using pypandoc."
    )
    parser.add_argument("--input", required=True, help="Path to input Markdown file")
    parser.add_argument("--output", required=True, help="Path to output DOCX file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}")
        return 1

    try:
        import pypandoc  # type: ignore
    except Exception as exc:  # noqa: BLE001
        print("[ERROR] pypandoc is not installed. Run: pip install pypandoc")
        print(f"Details: {exc}")
        return 1

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pypandoc.convert_file(
            source_file=str(input_path),
            to="docx",
            outputfile=str(output_path),
            extra_args=["--standalone"],
        )
    except OSError as exc:
        print("[ERROR] Pandoc is likely not installed or not found in PATH.")
        print("Download and install from: https://pandoc.org/installing.html")
        print(f"Details: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Failed to convert. Details: {exc}")
        return 1

    print(f"[OK] DOCX generated at: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
