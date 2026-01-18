# Главный движок
# Берет VideoObject, проходит по сценам (в будущем по актам), собирает слои и рендерит итоговое видео
# Использование типов данных из src.shemas
import os
from typing import List
import moviepy.video.fx as vfx
from moviepy.video.VideoClip import TextClip
from moviepy import * # MoviePy v2.0 imports

# подключаем схемы
from src.schemas.video_object import VideoObject
from src.schemas.scene_object import SceneObject
from src.schemas.annotation_object import AnnotationObject

# подключаем нашу рисовалку
from src.graphics_utils import (
    create_annotation_image,
    create_focus_mask,    
    create_text_bg,      
    ease_in_out         
)

def resolve_font(font_path: str | None) -> str:
    # гарантирует существующий шрифт для TextClip
    candidates = [
        font_path,
        "/usr/share/fonts/TTF/JetBrainsMono-ExtraBold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]

    for path in candidates:
        if path and os.path.exists(path):
            return path

    raise FileNotFoundError("Не найден ни один валидный шрифт для TextClip")


def process_screenshot_video(video: VideoObject, output_path: str):
    # главная функция: принимает объект видео, собирает сцены и рендерит файл
    print(f"--- Запуск генерации Screenshot Mode: {video.metadata.title} ---")
    
    # парсинг разрешение из метаданных "1920x1080" -> 1920, 1080
    res_w, res_h = map(int, video.metadata.resolution.lower().split('x'))
    fps = video.metadata.fps
    
    final_clips = []

    # проходимся по всем сценам из объекта VideoObject
    for i, scene in enumerate(video.scenes):
        print(f"Обработка сцены {i+1}/{len(video.scenes)}: {scene.path}")
        
        # 1. создаем базовый клип (фон)
        # используем ImageClip. т.к. мы работаем с объектом, путь берем через scene.path
        if not os.path.exists(scene.path):
            raise FileNotFoundError(f"Файл изображения не найден: {scene.path}")

        base_clip = (
            ImageClip(scene.path)
            .with_duration(scene.duration)
            .resized((res_w, res_h)) # подгоняем под разрешение проекта
        )

        # микродвижение — чтобы видео не было статичным
        base_clip = base_clip.resized(
            lambda t: round(1 + 0.015 * ease_in_out(min(t / scene.duration, 1)), 4)
        )



        # 2. применяем эффекты сцены (по ТЗ)
        if scene.effect == "black_white":
            base_clip = base_clip.with_effects([vfx.BlackAndWhite()])

        # список слоев для композитинга: [Фон, Аннотация1, Текст1, ...]
        layers = [base_clip]

        # затемнение фона, если есть аннотации или текст
        if scene.annotations or scene.texts:
            dim_clip = (
                ColorClip((res_w, res_h), color=(0, 0, 0))
                .with_opacity(0.35)
                .with_duration(scene.duration)
            )
            layers.append(dim_clip)

        # 3. обработка аннотаций (Annotations)
        # scene.annotations - это список объектов AnnotationObject
        for annot in scene.annotations:
            # auto-focus маска (если square)
            if annot.type == "square":
                focus_img = create_focus_mask(
                    res_w, res_h,
                    annot.start_x,
                    annot.start_y,
                    annot.end_x,
                    annot.end_y
                )

                focus_clip = (
                    ImageClip(focus_img)
                    .with_start(annot.wait)
                    .with_duration(
                        annot.duration if annot.duration > 0 else scene.duration - annot.wait
                    )
                )

                layers.append(focus_clip)

            # генерируем картинку с аннотацией через PIL
            annot_img = create_annotation_image(
                res_w, res_h, 
                annot.type, 
                (annot.start_x, annot.start_y), 
                (annot.end_x, annot.end_y)
            )
            
            # создаем клип аннотации
            annot_clip = (
                ImageClip(annot_img)
                .with_start(annot.wait) # задержка появления
                .with_duration(
                    annot.duration if annot.duration > 0 else scene.duration - annot.wait
                )
                .with_opacity(1.0 - annot.transparency) # прозрачность из ТЗ
            )

            # мягкое появление
            annot_clip = annot_clip.with_effects([
                vfx.FadeIn(0.3),
                vfx.FadeOut(0.3)
            ])

            layers.append(annot_clip)

        # 4. обработка текстов (Texts)
        # вадимка подготовил TextObject, реализуем его поддержку
        for text_obj in scene.texts:
            # в MoviePy v2 TextClip требует указания шрифта/метода
            txt_clip = TextClip(
                text=text_obj.text,
                font=resolve_font(text_obj.font),
                font_size=int(text_obj.size), 
                method='caption',
                size=(res_w * 8 // 10, None),
                color='white'                           
            )
            
            txt_clip = txt_clip.with_position(
                (int(text_obj.start_x), int(text_obj.start_y))
            )

            # умное позиционирование
            pos_x = (res_w - txt_clip.size[0]) // 2 if text_obj.start_x == "center" else text_obj.start_x
            pos_y = (res_h - txt_clip.size[1]) // 2 if text_obj.start_y == "center" else text_obj.start_y

            txt_clip = txt_clip.with_position((pos_x, pos_y))

            # подложка под текст
            bg_img = create_text_bg(
                res_w, res_h,
                text_obj.start_x,
                text_obj.start_y,
                txt_clip.size[0],
                txt_clip.size[1]
            )

            bg_clip = (
                ImageClip(bg_img)
                .with_start(text_obj.wait)
                .with_duration(
                    text_obj.duration if text_obj.duration > 0 else scene.duration - text_obj.wait
                )
                .with_effects([
                    vfx.FadeIn(0.4),
                    vfx.FadeOut(0.4)
                ])
            )

            layers.append(bg_clip)

            txt_clip = (
                txt_clip
                .with_duration(
                    text_obj.duration if text_obj.duration > 0 else scene.duration - text_obj.wait
                )
                .with_start(text_obj.wait)
                .with_position((text_obj.start_x, text_obj.start_y))
                .with_effects([
                    vfx.FadeIn(0.4),
                    vfx.FadeOut(0.4)
                ])
            )
            
            layers.append(txt_clip)

        # 5. сборка сцены (CompositeVideoClip)
        scene_composite = CompositeVideoClip(
            layers,
            size=(res_w, res_h)
        ).with_duration(scene.duration)

        
        # 6. обработка переходов (Transitions) согласно ТЗ
        # переходы применяются К ТЕКУЩЕМУ клипу при появлении
        # примечание: полноценные переходы (slide) в MoviePy делаются через padding
        # для MVP реализуем базовый Crossfade или простую склейку
        
        if scene.transition == "blackout":
            scene_composite = scene_composite.with_effects([
                vfx.FadeIn(scene.transpeed),
                vfx.FadeOut(scene.transpeed * 0.5)
            ])

        # (тут можно дописать slideRight/Left, если потребуется сложная логика)

        final_clips.append(scene_composite)

    # собираем финальное видео
    print("Склейка финального видео...")
    final_video = concatenate_videoclips(final_clips, method="compose")
    
    # экспорт
    output_file = os.path.join(output_path, f"{video.metadata.title}.mp4")
    print(f"Рендеринг в файл: {output_file}")
    
    final_video.write_videofile(
        output_file, 
        fps=fps, 
        codec="libx264",
        audio_codec="aac"
    )
    print("Готово!")
