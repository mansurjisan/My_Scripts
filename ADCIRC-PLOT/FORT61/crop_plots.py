#!/usr/bin/env python
import os
from PIL import Image
import glob

# Find all comparison plots
for filename in glob.glob("*_UND_vs_Mansur.png"):
    try:
        # Open image
        img = Image.open(filename)
        width, height = img.size
        
        # Crop to top half (overlay panel only)
        cropped = img.crop((0, 0, width, height//2))
        
        # Save with new name
        new_name = f"cropped_{filename}"
        cropped.save(new_name)
        print(f"Cropped {filename} -> {new_name}")
        
    except Exception as e:
        print(f"Error processing {filename}: {e}")

print("All images cropped!")
