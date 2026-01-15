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

### Specify output path
```bash
python svg_to_png.py image.svg -o custom_name.png
```

## Options

| Option | Description |
|--------|-------------|
| `-s, --scale` | Scale factor for resolution (default: 3.0) |
| `-o, --output` | Output file path (single file only) |

## Examples

```bash
# Convert at default 3x scale (high resolution)
python svg_to_png.py diagram.svg

# Convert at 5x scale for very high resolution
python svg_to_png.py diagram.svg -s 5

# Convert all SVGs in current directory
python svg_to_png.py *.svg

# Convert with custom output name
python svg_to_png.py input.svg -o output.png
```
