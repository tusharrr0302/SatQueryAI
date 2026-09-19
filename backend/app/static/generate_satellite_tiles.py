import math
import random
from PIL import Image, ImageDraw, ImageFilter

def create_delhi_image(year=2024, is_lush=True, width=800, height=600):
    # Base background: satellite palette (patchwork of fields and soil)
    img = Image.new("RGB", (width, height), (70, 75, 55))
    draw = ImageDraw.Draw(img)

    random.seed(42 + year)

    # 1. Agricultural patchwork fields
    step = 25
    for x in range(0, width, step):
        for y in range(0, height, step):
            # Distance from center (Delhi urban core)
            dx = (x - width * 0.45) / width
            dy = (y - height * 0.5) / height
            dist = math.sqrt(dx * dx + dy * dy)

            if dist > 0.22:
                # Agricultural/rural zone
                if is_lush:
                    r = random.randint(35, 65)
                    g = random.randint(90, 150)
                    b = random.randint(30, 55)
                else:
                    r = random.randint(85, 125)
                    g = random.randint(90, 115)
                    b = random.randint(60, 85)
                draw.rectangle([x, y, x + step, y + step], fill=(r, g, b), outline=(40, 45, 30))

    # 2. Urban core (gray / concrete / built-up)
    urban_radius = 180 if year >= 2024 else 140
    for _ in range(12000):
        ux = random.gauss(width * 0.46, urban_radius * 0.45)
        uy = random.gauss(height * 0.52, urban_radius * 0.45)
        if 0 <= ux < width and 0 <= uy < height:
            gray = random.randint(110, 165)
            tint = random.randint(-8, 8)
            draw.point((ux, uy), fill=(gray + tint, gray + tint, gray + 5))

    # Dense blocks in urban core
    for _ in range(80):
        bx = random.gauss(width * 0.45, urban_radius * 0.35)
        by = random.gauss(height * 0.52, urban_radius * 0.35)
        bw = random.randint(8, 28)
        bh = random.randint(8, 28)
        g_val = random.randint(120, 180)
        draw.rectangle([bx, by, bx + bw, by + bh], fill=(g_val, g_val - 2, g_val + 4), outline=(90, 90, 95))

    # 3. Roads / Expressways
    # Ring road / Radial arterial roads
    road_color = (190, 190, 195)
    center_pt = (int(width * 0.46), int(height * 0.52))
    for angle in [0.2, 0.8, 1.4, 2.1, 2.9, 3.8, 4.7, 5.5]:
        ex = int(center_pt[0] + math.cos(angle) * width * 0.6)
        ey = int(center_pt[1] + math.sin(angle) * height * 0.6)
        draw.line([center_pt, (ex, ey)], fill=road_color, width=2)

    # 4. Yamuna River (meandering from top to bottom)
    river_color = (25, 45, 65)
    points = []
    rx = width * 0.56
    for y in range(0, height, 15):
        rx += math.sin(y * 0.015) * 4.0 + math.cos(y * 0.03) * 3.0
        points.append((rx, y))
    draw.line(points, fill=river_color, width=12)
    draw.line(points, fill=(15, 30, 48), width=6)

    # Smooth slightly for natural satellite optical look
    img = img.filter(ImageFilter.GaussianBlur(radius=0.7))
    return img


def main():
    import os
    out_dir = os.path.join(os.path.dirname(__file__), "images")
    os.makedirs(out_dir, exist_ok=True)

    # Delhi 2023 (less green)
    delhi_2023 = create_delhi_image(2023, is_lush=False)
    delhi_2023.save(os.path.join(out_dir, "delhi_2023.jpg"), quality=92)

    # Delhi 2024 (lush green, matching screenshot)
    delhi_2024 = create_delhi_image(2024, is_lush=True)
    delhi_2024.save(os.path.join(out_dir, "delhi_2024.jpg"), quality=92)

    # Delhi 2016 (smaller urban footprint)
    delhi_2016 = create_delhi_image(2016, is_lush=False)
    delhi_2016.save(os.path.join(out_dir, "delhi_2016.jpg"), quality=92)

    # Delhi 2026 (sprawling urban footprint)
    delhi_2026 = create_delhi_image(2026, is_lush=True)
    delhi_2026.save(os.path.join(out_dir, "delhi_2026.jpg"), quality=92)

    # Amazon 2021 & 2024
    img_amz1 = Image.new("RGB", (800, 600), (20, 75, 25))
    d1 = ImageDraw.Draw(img_amz1)
    for _ in range(4000):
        d1.point((random.randint(0, 800), random.randint(0, 600)), fill=(random.randint(15, 35), random.randint(65, 110), random.randint(20, 40)))
    img_amz1.save(os.path.join(out_dir, "amazon_2021.jpg"), quality=90)

    img_amz2 = img_amz1.copy()
    d2 = ImageDraw.Draw(img_amz2)
    for _ in range(25):
        cx = random.randint(200, 600)
        cy = random.randint(150, 450)
        d2.rectangle([cx, cy, cx + random.randint(40, 100), cy + random.randint(20, 60)], fill=(160, 130, 90))
    img_amz2.save(os.path.join(out_dir, "amazon_2024.jpg"), quality=90)

    # Punjab Nov & Mar
    delhi_2023.save(os.path.join(out_dir, "punjab_nov.jpg"), quality=90)
    delhi_2024.save(os.path.join(out_dir, "punjab_mar.jpg"), quality=90)

    # Derna pre & post
    img_derna1 = Image.new("RGB", (800, 600), (160, 140, 110))
    img_derna1.save(os.path.join(out_dir, "derna_pre.jpg"), quality=90)
    img_derna2 = Image.new("RGB", (800, 600), (90, 80, 70))
    d_post = ImageDraw.Draw(img_derna2)
    d_post.polygon([(300, 0), (500, 0), (600, 600), (200, 600)], fill=(45, 60, 80))
    img_derna2.save(os.path.join(out_dir, "derna_post.jpg"), quality=90)

    print("Satellite image tiles generated successfully!")


if __name__ == "__main__":
    main()
