#!/usr/bin/env python3
"""Convert SVG files to high-resolution PNG images."""

import argparse
import sys
from pathlib import Path

try:
    import cairosvg
except ImportError:
    print("Error: cairosvg not installed. Run: pip install cairosvg")
    sys.exit(1)


def convert_svg_to_png(svg_path: str, output_path: str = None, scale: float = 3.0):
    """Convert an SVG file to PNG.

    Args:
        svg_path: Path to the input SVG file
        output_path: Path for the output PNG (default: same name with .png extension)
        scale: Scale factor for resolution (default: 3.0 for high-res)
    """
    svg_path = Path(svg_path)

    if not svg_path.exists():
        print(f"Error: {svg_path} not found")
        return False

    if output_path is None:
        output_path = svg_path.with_suffix('.png')
    else:
        output_path = Path(output_path)

    try:
        cairosvg.svg2png(url=str(svg_path), write_to=str(output_path), scale=scale)
        print(f"Converted: {svg_path.name} -> {output_path.name}")
        return True
    except Exception as e:
        print(f"Error converting {svg_path}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Convert SVG files to high-resolution PNG")
    parser.add_argument("files", nargs="+", help="SVG file(s) to convert")
    parser.add_argument("-s", "--scale", type=float, default=3.0,
                        help="Scale factor (default: 3.0 for high-res)")
    parser.add_argument("-o", "--output", help="Output path (only for single file)")

    args = parser.parse_args()

    if args.output and len(args.files) > 1:
        print("Error: --output can only be used with a single input file")
        sys.exit(1)

    success = 0
    for svg_file in args.files:
        output = args.output if len(args.files) == 1 else None
        if convert_svg_to_png(svg_file, output, args.scale):
            success += 1

    print(f"\nConverted {success}/{len(args.files)} files")


if __name__ == "__main__":
    main()
