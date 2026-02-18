import os
from PIL import Image, ImageDraw

def create_placeholder(filename, color, text):
    # холст 1920x1080
    img = Image.new('RGB', (1920, 1080), color=color)
    draw = ImageDraw.Draw(img)
    
    # текст в центре
    draw.text((800, 500), text, fill=(255, 255, 255))
    
    if not os.path.exists('input'):
        os.makedirs('input')
        
    path = os.path.join('input', filename)
    img.save(path)
    print(f"Файл создан: {path}")

if __name__ == "__main__":
    # два файла, которые нужны для demo_script.yaml
    create_placeholder("bg_main.png", (45, 52, 54), "MAIN BACKGROUND (Scene 1 & 3)")
    create_placeholder("login_screen.png", (9, 132, 227), "LOGIN SCREEN (Scene 2)")