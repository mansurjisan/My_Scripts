import os
import glob
from PIL import Image
import re

def extract_station_name(filename):
    """Extract station name from filename for use as page title"""
    # Pattern to extract the station name between __ and _UND
    match = re.search(r'__(.+?)_UND', filename)
    if match:
        return match.group(1).replace('_', ' ')
    return os.path.basename(filename)

def create_pdf_from_pngs(input_folder='.', output_pdf='combined_cropped_images.pdf', 
                         sort_by_name=True, add_titles=True, images_per_page=1):
    """
    Combine all PNG files starting with 'cropped_' into a single PDF
    
    Parameters:
    - input_folder: Folder containing the PNG files (default: current directory)
    - output_pdf: Name of the output PDF file
    - sort_by_name: Sort images alphabetically by filename
    - add_titles: Add station names as titles on each page
    - images_per_page: Number of images per page (1 or 2 recommended)
    """
    
    # Find all PNG files starting with 'cropped_'
    pattern = os.path.join(input_folder, 'cropped_*.png')
    png_files = glob.glob(pattern)
    
    if not png_files:
        print(f"No PNG files found matching pattern: {pattern}")
        return False
    
    print(f"Found {len(png_files)} PNG files to process")
    
    # Sort files if requested
    if sort_by_name:
        png_files.sort()
    
    # Convert images to PIL Image objects and process
    images = []
    
    for i, png_file in enumerate(png_files):
        print(f"Processing {i+1}/{len(png_files)}: {os.path.basename(png_file)}")
        
        try:
            img = Image.open(png_file)
            
            # Convert RGBA to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'RGBA':
                    rgb_img.paste(img, mask=img.split()[3])  # Use alpha channel as mask
                else:
                    rgb_img.paste(img)
                img = rgb_img
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Optionally add title at the top of the image
            if add_titles:
                from PIL import ImageDraw, ImageFont
                
                title = extract_station_name(png_file)
                
                # Create a new image with space for title
                new_height = img.height + 50
                new_img = Image.new('RGB', (img.width, new_height), (255, 255, 255))
                
                # Add title
                draw = ImageDraw.Draw(new_img)
                try:
                    # Try to use a nice font, fall back to default if not available
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
                except:
                    font = ImageFont.load_default()
                
                # Center the text
                text_bbox = draw.textbbox((0, 0), title, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_x = (img.width - text_width) // 2
                draw.text((text_x, 10), title, fill=(0, 0, 0), font=font)
                
                # Paste original image below title
                new_img.paste(img, (0, 50))
                img = new_img
            
            images.append(img)
            
        except Exception as e:
            print(f"Error processing {png_file}: {e}")
            continue
    
    if not images:
        print("No images could be processed successfully")
        return False
    
    # Save all images as PDF
    print(f"\nCreating PDF: {output_pdf}")
    
    # The first image is saved with all others appended
    if len(images) == 1:
        images[0].save(output_pdf, "PDF", resolution=100.0)
    else:
        images[0].save(output_pdf, "PDF", resolution=100.0, save_all=True, append_images=images[1:])
    
    print(f"✓ PDF created successfully: {output_pdf}")
    print(f"  Total pages: {len(images)}")
    
    # Print summary of included files
    print("\nIncluded files:")
    for i, png_file in enumerate(png_files[:5]):
        print(f"  {i+1}. {os.path.basename(png_file)}")
    if len(png_files) > 5:
        print(f"  ... and {len(png_files) - 5} more files")
    
    return True

def main():
    """Main function with example usage"""
    
    # Basic usage - combines all cropped_*.png files in current directory
    create_pdf_from_pngs()
    
    # Advanced usage with custom settings
    # create_pdf_from_pngs(
    #     input_folder='/path/to/your/images',
    #     output_pdf='ADCIRC_stations_comparison.pdf',
    #     sort_by_name=True,
    #     add_titles=True
    # )

if __name__ == "__main__":
    main()
