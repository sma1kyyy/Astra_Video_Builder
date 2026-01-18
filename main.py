from src.parser import parse
from src.screen_recorder import start_record
from src.browser_engine import start_actions

def main():
    print("Hello from astra-stipendiya-generirovanie-demonstracionnyh-rolikov-s-pomoshchu-skriptov!")


if __name__ == "__main__":
    video = parse("test/test.yaml")
    # start_record(video.metadata)
    for scene in video.scenes:
        start_actions(scene.actions)

# from script_parser import load_script
# from timeline_builder import build_timeline
# from screenshot_mode import process_screenshots
# from video_renderer import render_video

# def main():
#     script = load_script("scripts/demo_script.json")
#     timeline = build_timeline(script)
#     frames = process_screenshots(timeline)
#     render_video(frames, "output/demo.mp4")

# if __name__ == "__main__":
#     main()