import cv2
import pytesseract
from .preprocess import preprocess_for_ocr
from .vision_types import BBox

def extract_text_data(image_path: str):
    image = cv2.imread(image_path)
    processed = preprocess_for_ocr(image)

    data = pytesseract.image_to_data(
        processed,
        lang="rus+eng",
        output_type=pytesseract.Output.DICT
    )

    results = []

    for i, text in enumerate(data["text"]):
        if text.strip():
            bbox = BBox(
                x=data["left"][i],
                y=data["top"][i],
                width=data["width"][i],
                height=data["height"][i],
            )

            results.append({
                "text": text,
                "confidence": data["conf"][i],
                "bbox": bbox
            })

    return results