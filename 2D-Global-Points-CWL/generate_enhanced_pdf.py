#!/usr/bin/env python3
"""
Generate PDF from enhanced STOFS-2D maxele difference plots
Combines all regional plots for a given date and cycle into a single PDF
"""

import os
import sys
from PIL import Image
import argparse

# Region order for PDF pages
REGIONS = [
    "us_east_coast",
    "chesapeake_bay",
    "new_york_harbor",
    "boston_harbor",
    "delaware_bay",
    "tampa_bay",
    "galveston_bay",
    "mobile_bay",
    "puget_sound",
    "puerto_rico",
    "conus",
    "global"
]


def create_pdf(date, cycle, base_dir, output_dir):
    """Create PDF from enhanced PNG plots."""
    plots_dir = os.path.join(base_dir, date, "plots", f"{date}_{cycle}z")

    if not os.path.exists(plots_dir):
        print(f"Directory not found: {plots_dir}")
        return False

    # Collect images
    images = []
    for region in REGIONS:
        png_file = os.path.join(plots_dir, f"t{cycle}z_{region}_enhanced.png")
        if os.path.exists(png_file):
            try:
                img = Image.open(png_file)
                # Convert to RGB if necessary (for RGBA images)
                if img.mode == 'RGBA':
                    # Create white background
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                images.append(img)
                print(f"  Added: {region}")
            except Exception as e:
                print(f"  Error loading {region}: {e}")
        else:
            print(f"  Missing: {region}")

    if not images:
        print(f"No images found for {date} t{cycle}z")
        return False

    # Create output directory if needed
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Save as PDF
    output_file = os.path.join(output_dir, f"{date}_t{cycle}z_enhanced.pdf")

    # First image is the cover, rest are appended
    images[0].save(
        output_file,
        "PDF",
        resolution=300.0,
        save_all=True,
        append_images=images[1:]
    )

    print(f"Created: {output_file} ({len(images)} pages)")
    return True


def main():
    parser = argparse.ArgumentParser(description='Generate PDF from enhanced plots')
    parser.add_argument('date', help='Date in YYYYMMDD format')
    parser.add_argument('--cycle', default=None, help='Specific cycle (00, 06, 12, 18) or all')
    parser.add_argument('--base-dir', default='/mnt/d/STOFS2D-Analysis/MAXELE_PLOTS',
                        help='Base directory for plots')
    parser.add_argument('--output-dir', default=None,
                        help='Output directory for PDFs (default: base_dir/PDFs)')

    args = parser.parse_args()

    if args.output_dir is None:
        args.output_dir = os.path.join(args.base_dir, "PDFs")

    cycles = [args.cycle] if args.cycle else ["00", "06", "12", "18"]

    for cycle in cycles:
        print(f"\n=== Processing {args.date} t{cycle}z ===")
        create_pdf(args.date, cycle, args.base_dir, args.output_dir)

    print("\n=== Done ===")


if __name__ == '__main__':
    main()
