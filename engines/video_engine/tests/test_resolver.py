from annotations.annotation_resolver import resolve_text_target

bbox = resolve_text_target(
    "test.png",
    target_text="Войти",
    padding=20
)

print(bbox)