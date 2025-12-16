#построение самих сцен

def build_timeline(script):
    timeline = []

    for scene in script["scenes"]:
        timeline.append({
            "image": scene["image"],
            "duration": scene["duration"]
        })

    return timeline
