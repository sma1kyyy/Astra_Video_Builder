#структура генерации видео

from moviepy import ImageClip, concatenate_videoclips

def render_video(timeline, output):
    clips = []

    for scene in timeline:
        clip = ImageClip(scene["image"]).with_duration(scene["duration"])
        clips.append(clip)

    video = concatenate_videoclips(clips)
    video.write_videofile(output, fps=24)
