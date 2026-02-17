from difflib import SequenceMatcher

def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_best_match(target, extracted, threshold=0.75):
    best = None
    best_score = 0

    for item in extracted:
        score = similarity(target, item["text"])

        if score > threshold and score > best_score:
            best = item
            best_score = score

    return best