from vision.ocr_engine import extract_text_data

data = extract_text_data("src/input/creen2.png")

for item in data:
    print(item["text"], item["bbox"])