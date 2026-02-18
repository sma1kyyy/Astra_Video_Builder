from vision import (
    extract_text_data,
    find_best_match,
    apply_padding,
    get_cached,
    set_cached,
)

def resolve_text_target(image_path: str, target_text: str, padding: int = 0):
    cached = get_cached(image_path)

    if not cached:
        extracted = extract_text_data(image_path)
        set_cached(image_path, extracted)
    else:
        extracted = cached

    match = find_best_match(target_text, extracted)

    if not match:
        return None

    bbox = match["bbox"]

    if padding:
        bbox = apply_padding(bbox, padding)

    return bbox