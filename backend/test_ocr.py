"""Test Azure Document Intelligence with the user's actual PDF."""
import sys, os, time
sys.path.insert(0, os.getcwd())

# Use the actual AzureOCRService from the codebase
from utils.azure_ocr_service import get_azure_ocr_service

file_path = r"C:\Users\acer\Downloads\PublicWaterMassMailing.pdf"

print("=" * 60)
print("Testing Azure Document Intelligence OCR")
print("=" * 60)
print(f"File: {file_path}")
print(f"Exists: {os.path.exists(file_path)}")
print(f"Size: {os.path.getsize(file_path) / 1024:.1f} KB")
print()

service = get_azure_ocr_service()
if service is None:
    print("ERROR: Azure OCR service not configured!")
    sys.exit(1)

print(f"Service endpoint: {service.endpoint}")
print(f"Analyze URL: {service.analyze_url}")
print()

print("Starting OCR extraction...")
start = time.time()
result = service.extract_text_sync(file_path)
elapsed = time.time() - start

print(f"\nCompleted in {elapsed:.1f}s")
if result:
    print(f"SUCCESS! Extracted {len(result)} characters")
    print(f"\nFirst 800 chars:\n{'─' * 40}")
    print(result[:800])
    print(f"{'─' * 40}")
else:
    print("FAILED: No text extracted")