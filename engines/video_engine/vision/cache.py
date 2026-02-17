_ocr_cache = {}

def get_cached(image_path):
    return _ocr_cache.get(image_path)

def set_cached(image_path, data):
    _ocr_cache[image_path] = data