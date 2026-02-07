import os
import json
import easyocr
import glob
from PIL import Image
import numpy as np

# Configuration
ROOT_DIR = '.'  # Current directory
OUTPUT_FILE = 'ocr_data.js'
LANGUAGES = ['ja', 'en']

def load_existing_data(filepath):
    """Loads existing OCR data from the JS file if it exists."""
    if not os.path.exists(filepath):
        return {}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            # Expecting format: const OCR_DATA = { ... };
            # We strip the prefix and suffix to parse JSON
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
    print("Initializing EasyOCR reader...")
    # gpu=True if CUDA is available, else False. EasyOCR handles this automatically usually.
    reader = easyocr.Reader(LANGUAGES)
    
    existing_data = load_existing_data(OUTPUT_FILE)
    print(f"Loaded {len(existing_data)} entries from existing database.")
    
    # Find all webp files recursively
    # Windows path separator might be backslash, but web use forward slash.
    # We'll normalize paths to forward slashes for the JS key.
    all_files = glob.glob('**/*.webp', recursive=True)
    
    # Filter files that need processing
    files_to_process = []
    for f_path in all_files:
        # Normalize path to standard forward slash relative to root
        rel_path = f_path.replace(os.sep, '/')
        if rel_path not in existing_data:
            files_to_process.append((f_path, rel_path))
            
    total_new = len(files_to_process)
    print(f"Found {len(all_files)} images total. {total_new} new images to process.")
    
    if total_new == 0:
        print("No new images to process.")
        return

    processed_count = 0
    save_interval = 20 # Save every 20 images
    
    try:
        for f_path, rel_path in files_to_process:
            print(f"Processing ({processed_count + 1}/{total_new}): {rel_path}")
            
            try:
                # Detail=0 for simple text output
                # Fix for Japanese paths on Windows: Read with PIL and convert to numpy
                # OpenCV (used by easyocr) often fails with non-ASCII paths on Windows
                with Image.open(f_path) as img:
                    img_np = np.array(img.convert('RGB'))
                
                result = reader.readtext(
                    img_np, 
                    detail=0, 
                    mag_ratio=3.0, 
                    beamWidth=20, 
                    rotation_info=[90, 180, 270],
                    text_threshold=0.5, 
                    low_text=0.3, 
                    contrast_ths=0.1, 
                    adjust_contrast=0.5
                )
                # Join text and also include the filename in the search text
                # Normalize text to lower case for case-insensitive search logic might be handled in JS, 
                # but storing raw text is better.
                full_text = " ".join(result) + " " + os.path.basename(f_path)
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
