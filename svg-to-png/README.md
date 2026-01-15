# SVG to PNG Converter

A Python script to convert SVG files to high-resolution PNG images using Cairo.

## Requirements

- Python 3.6+
- cairosvg

## Installation

```bash
pip install cairosvg
```

## Usage

### Basic usage (single file)
```bash
python svg_to_png.py image.svg
```

### Convert multiple files
```bash
python svg_to_png.py *.svg
```

### Custom scale factor
Default scale is 3x. Use `-s` or `--scale` to adjust:
```bash
python svg_to_png.py image.svg -s 5
```

### Custom DPI
Use `-d` or `--dpi` for specific DPI output:
```bash
python svg_to_png.py image.svg -d 300   # print quality
python svg_to_png.py image.svg -d 600   # high-quality print
```

### Specify output path
```bash
python svg_to_png.py image.svg -o custom_name.png
```

## Options

| Option | Description |
|--------|-------------|
| `-s, --scale` | Scale factor for resolution (default: 3.0) |
| `-d, --dpi` | DPI for output (96=standard, 300=print, 600=high-quality) |
| `-o, --output` | Output file path (single file only) |

## Examples

```bash
# Convert at default 3x scale (high resolution)
python svg_to_png.py diagram.svg

# Convert at 5x scale for very high resolution
python svg_to_png.py diagram.svg -s 5

# Convert at 300 DPI (print quality)
python svg_to_png.py diagram.svg -d 300

# Convert at 600 DPI (high-quality print)
python svg_to_png.py diagram.svg -d 600

# Convert all SVGs in current directory
python svg_to_png.py *.svg

# Convert with custom output name
python svg_to_png.py input.svg -o output.png
```
