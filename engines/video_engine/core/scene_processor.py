bbox = resolve_text_target(
    scene.image_path,
    highlight.target_text,
    padding=highlight.padding
)

clip = render_highlight(scene, bbox)