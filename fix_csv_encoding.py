#!/usr/bin/env python3
"""
Script to fix CSV encoding issues by converting to proper UTF-8
"""
import csv
import os

def fix_csv_encoding(input_file, output_file=None):
    """
    Fix CSV encoding by trying multiple encodings and saving as UTF-8
    """
    if output_file is None:
        name, ext = os.path.splitext(input_file)
        output_file = f"{name}_fixed{ext}"
    
    # List of encodings to try
    encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    
    content = None
    used_encoding = None
    
    # Try to read with different encodings
    for encoding in encodings:
        try:
            with open(input_file, 'r', encoding=encoding) as f:
                content = f.read()
                used_encoding = encoding
                print(f"Successfully read file using {encoding} encoding")
                break
        except UnicodeDecodeError:
            continue
    
    if content is None:
        print("Error: Could not read file with any encoding")
        return False
    
    # Write as UTF-8
    try:
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            f.write(content)
        print(f"File saved as {output_file} with UTF-8 encoding")
        return True
    except Exception as e:
        print(f"Error saving file: {e}")
        return False

def fix_harvest_records_csv():
    """
    Fix the specific harvest records CSV file
    """
    input_file = "harvest_records_template (2) pang distribution lang.csv"
    output_file = "harvest_records_template_fixed.csv"
    
    if not os.path.exists(input_file):
        print(f"Error: File '{input_file}' not found")
        return False
    
    print(f"Fixing encoding for: {input_file}")
    success = fix_csv_encoding(input_file, output_file)
    
    if success:
        print(f"\n✅ Success! Use the file '{output_file}' for uploading.")
        print("This file now has proper UTF-8 encoding and should work with the upload feature.")
    
    return success

if __name__ == "__main__":
    fix_harvest_records_csv()