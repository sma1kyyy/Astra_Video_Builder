from moviepy.editor import ImageClip
from annotations.annotation_resolver import resolve_text_target
from annotations.highlight_renderer import render_highlight

image_path = "test.png"

base = ImageClip(image_path).set_duration(3)

bbox = resolve_text_target(image_path, "Войти", padding=20)

final = render_highlight(base, bbox, duration=3)

final.write_videofile("output.mp4", fps=30)