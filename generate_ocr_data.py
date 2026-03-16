import os
import json
import easyocr
import glob
from PIL import Image
import numpy as np
import psutil
import torch
import logging
from manga_ocr import MangaOcr

# Configuration
ROOT_DIR = '.'  # Current directory
OUTPUT_FILE = 'ocr_data.js'

# Set logging levels to reduce noise
logging.getLogger("manga_ocr").setLevel(logging.WARNING)

def load_existing_data(filepath):
    """Loads existing OCR data from the JS file if it exists."""
    if not os.path.exists(filepath):
        return {}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            # Expecting format: const OCR_DATA = { ... };
            prefix = 'const OCR_DATA = '
            suffix = ';'
            if content.startswith(prefix):
                json_str = content[len(prefix):].strip().rstrip(suffix)
                return json.loads(json_str)
    except Exception as e:
        print(f"Warning: Could not load existing data: {e}")
    
    return {}

def save_data(data, filepath):
    """Saves the OCR data to a JS file as a global variable."""
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    content = f"const OCR_DATA = {json_str};"
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Saved progress to {filepath}")

def main():
    print("Initializing OCR engines...")
    # Get total logical cores and use all of them
    total_cores = psutil.cpu_count(logical=True)
    target_threads = max(1, total_cores)
    print(f"Configuring CPU resources: torch.set_num_threads({target_threads})")
    torch.set_num_threads(target_threads)
    
    # Initialize EasyOCR (primarily for text detection)
    reader = easyocr.Reader(['ja', 'en'])
    # Initialize MangaOCR (for high-accuracy Japanese recognition, including vertical text)
    mocr = MangaOcr()
    
    existing_data = load_existing_data(OUTPUT_FILE)
    print(f"Loaded {len(existing_data)} entries from existing database.")
    
    # Find all webp files recursively
    all_files = glob.glob('**/*.webp', recursive=True)
    
    # Filter files that need processing
    files_to_process = []
    for f_path in all_files:
        rel_path = f_path.replace(os.sep, '/')
        if rel_path not in existing_data:
            files_to_process.append((f_path, rel_path))
            
    total_new = len(files_to_process)
    print(f"Found {len(all_files)} images total. {total_new} new images to process.")
    
    if total_new == 0:
        print("No new images to process.")
        return

    processed_count = 0
    save_interval = 10 # Save every 10 images
    
    try:
        for f_path, rel_path in files_to_process:
            print(f"Processing ({processed_count + 1}/{total_new}): {rel_path}")
            
            try:
                with Image.open(f_path) as img:
                    img_rgb = img.convert('RGB')
                    img_np = np.array(img_rgb)
                
                # Step 1: Detect text regions using EasyOCR
                # Increase mag_ratio and lower thresholds to pick up smaller/fainter text
                results = reader.readtext(
                    img_np, 
                    paragraph=False, 
                    mag_ratio=2.5, 
                    text_threshold=0.4, 
                    low_text=0.3, 
                    min_size=2
                )
                
                texts = []
                for (bbox, _, _) in results:
                    # Step 2: For each detected region, use Manga-OCR for recognition
                    # bbox is [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                    x_coords = [p[0] for p in bbox]
                    y_coords = [p[1] for p in bbox]
                    
                    x_min, x_max = max(0, int(min(x_coords))), int(max(x_coords))
                    y_min, y_max = max(0, int(min(y_coords))), int(max(y_coords))
                    
                    # Add a small padding (5px) for better Manga-OCR accuracy
                    padding = 5
                    width, height = img_rgb.size
                    x_min = max(0, x_min - padding)
                    y_min = max(0, y_min - padding)
                    x_max = min(width, x_max + padding)
                    y_max = min(height, y_max + padding)
                    
                    # Crop and recognize
                    if x_max > x_min and y_max > y_min:
                        crop = img_rgb.crop((x_min, y_min, x_max, y_max))
                        text = mocr(crop)
                        if text:
                            texts.append(text)
                
                # Join text and also include the filename in the search text
                full_text = " ".join(texts) + " " + os.path.basename(f_path)
                existing_data[rel_path] = full_text
                
                processed_count += 1
                
                if processed_count % save_interval == 0:
                    save_data(existing_data, OUTPUT_FILE)
                    
            except Exception as e:
                print(f"Error processing {f_path}: {e}")
                
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Saving current progress...")
    finally:
        save_data(existing_data, OUTPUT_FILE)
        print("Done.")

if __name__ == "__main__":
    main()
