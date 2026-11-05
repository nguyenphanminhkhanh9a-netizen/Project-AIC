"""Generates the 5 Core Pack RGBA WebP sprites for Nakano Miku.

Creates valid, high-resolution (1024x1536) transparent WebP images with:
- Signature Miku visual identity: Auburn/brownish hair, wireless triangle-motif headphones,
  navy/blue cardigan sweater over white collared shirt, and characteristic expressions.
- Full alpha transparency on background.
- Specific distinct expressions:
  1. idle_neutral: Standard calm, gentle gaze.
  2. happy: Bright eyes, warm smile, speaking state.
  3. pout: Iconic puffed cheeks pout, slight blush.
  4. blush_shy: Strong pink blush, shy eyes, timid pose.
  5. comforting: Gentle warm smile, supportive gesture.
"""

from pathlib import Path

from PIL import Image, ImageDraw


def draw_miku_sprite(
    expression_name: str,
    blush: bool = False,
    pout: bool = False,
    smile: bool = False,
    open_mouth: bool = False,
    sparkle: bool = False,
) -> Image.Image:
    """Renders a procedural anime sprite with Miku Nakano characteristics."""
    width, height = 1024, 1536
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    hair_color = (185, 75, 95, 255)
    hair_shadow = (145, 55, 75, 255)
    skin_color = (255, 238, 227, 255)
    skin_shadow = (245, 215, 200, 255)
    cardigan_color = (48, 64, 102, 255)
    shirt_white = (248, 248, 252, 255)
    headphone_band = (45, 45, 52, 255)
    headphone_cyan = (68, 175, 230, 255)
    eye_blue = (60, 110, 185, 255)

    # 1. Back hair
    draw.polygon(
        [
            (320, 480), (250, 850), (280, 1200), (380, 1300),
            (644, 1300), (744, 1200), (774, 850), (704, 480),
        ],
        fill=hair_shadow,
    )
    draw.polygon(
        [
            (340, 500), (270, 850), (300, 1150), (400, 1250),
            (624, 1250), (724, 1150), (754, 850), (684, 500),
        ],
        fill=hair_color,
    )

    # 2. Torso / Cardigan
    draw.polygon(
        [
            (330, 720), (240, 1000), (210, 1450), (814, 1450),
            (784, 1000), (694, 720), (512, 750),
        ],
        fill=cardigan_color,
    )
    draw.polygon([(440, 680), (512, 880), (584, 680)], fill=shirt_white)
    draw.polygon([(500, 730), (524, 730), (518, 860), (506, 860)], fill=(50, 90, 150, 255))

    # 3. Neck
    draw.rectangle([470, 580, 554, 700], fill=skin_shadow)
    draw.rectangle([480, 590, 544, 690], fill=skin_color)

    # 4. Wireless Headphones
    draw.arc([370, 600, 654, 720], start=0, end=180, fill=headphone_band, width=28)
    draw.rounded_rectangle([340, 600, 410, 710], radius=16, fill=headphone_band)
    draw.rounded_rectangle([350, 615, 400, 695], radius=10, fill=headphone_cyan)
    draw.polygon([(365, 665), (385, 665), (375, 645)], fill=headphone_band)

    draw.rounded_rectangle([614, 600, 684, 710], radius=16, fill=headphone_band)
    draw.rounded_rectangle([624, 615, 674, 695], radius=10, fill=headphone_cyan)
    draw.polygon([(639, 665), (659, 665), (649, 645)], fill=headphone_band)

    # 5. Face
    draw.ellipse([370, 320, 654, 620], fill=skin_color)
    draw.polygon([(410, 520), (512, 630), (614, 520)], fill=skin_color)

    # 6. Bangs
    draw.polygon(
        [
            (360, 320), (450, 250), (560, 250), (660, 320),
            (680, 440), (630, 510), (580, 430), (550, 540),
            (510, 420), (460, 510), (410, 420), (340, 440),
        ],
        fill=hair_color,
    )
    draw.polygon([(560, 330), (605, 520), (575, 490)], fill=hair_color)

    # 7. Eyes
    draw.ellipse([420, 440, 470, 475], fill=(255, 255, 255, 255))
    draw.ellipse([432, 443, 462, 473], fill=eye_blue)
    draw.ellipse([442, 447, 452, 457], fill=(255, 255, 255, 255))

    draw.ellipse([540, 440, 590, 475], fill=(255, 255, 255, 255))
    draw.ellipse([550, 443, 580, 473], fill=eye_blue)
    draw.ellipse([560, 447, 570, 457], fill=(255, 255, 255, 255))

    # Eyebrows
    if pout:
        draw.line([(420, 428), (470, 435)], fill=hair_shadow, width=5)
        draw.line([(540, 435), (590, 428)], fill=hair_shadow, width=5)
    else:
        draw.arc([418, 415, 472, 435], start=190, end=350, fill=hair_shadow, width=4)
        draw.arc([538, 415, 592, 435], start=190, end=350, fill=hair_shadow, width=4)

    # 8. Nose
    draw.line([(512, 490), (510, 496)], fill=(220, 160, 150, 255), width=3)

    # 9. Mouth
    if pout:
        draw.ellipse([502, 532, 522, 548], fill=(235, 120, 130, 255))
        draw.arc([385, 480, 420, 530], start=100, end=260, fill=(240, 150, 150, 255), width=4)
        draw.arc([604, 480, 639, 530], start=280, end=440, fill=(240, 150, 150, 255), width=4)
    elif smile and open_mouth:
        draw.chord([495, 520, 535, 555], start=0, end=180, fill=(210, 80, 95, 255))
        draw.chord([502, 520, 528, 532], start=0, end=180, fill=(255, 255, 255, 255))
    elif smile:
        draw.arc([495, 520, 535, 546], start=20, end=160, fill=(180, 80, 90, 255), width=4)
    else:
        draw.line([(500, 535), (524, 535)], fill=(180, 90, 100, 255), width=4)

    # 10. Blush
    if blush or pout:
        blush_opacity = 210 if blush else 140
        blush_color = (255, 150, 165, blush_opacity)
        draw.ellipse([405, 485, 465, 510], fill=blush_color)
        draw.line([(420, 490), (430, 505)], fill=(240, 100, 120, blush_opacity), width=3)
        draw.line([(435, 490), (445, 505)], fill=(240, 100, 120, blush_opacity), width=3)
        draw.line([(450, 490), (460, 505)], fill=(240, 100, 120, blush_opacity), width=3)

        draw.ellipse([550, 485, 610, 510], fill=blush_color)
        draw.line([(565, 490), (575, 505)], fill=(240, 100, 120, blush_opacity), width=3)
        draw.line([(580, 490), (590, 505)], fill=(240, 100, 120, blush_opacity), width=3)
        draw.line([(595, 490), (605, 505)], fill=(240, 100, 120, blush_opacity), width=3)

    # 11. Sparkles
    if sparkle:
        def draw_sparkle(cx: int, cy: int, r: int) -> None:
            sparkle_col = (255, 245, 180, 230)
            draw.line([(cx - r, cy), (cx + r, cy)], fill=sparkle_col, width=3)
            draw.line([(cx, cy - r), (cx, cy + r)], fill=sparkle_col, width=3)

        draw_sparkle(340, 400, 18)
        draw_sparkle(680, 390, 14)
        draw_sparkle(300, 520, 12)

    # 12. Bottom badge indicator
    badge_bg = (30, 35, 50, 180)
    badge_text = f"Miku Nakano • {expression_name}"
    draw.rounded_rectangle([260, 1460, 764, 1510], radius=12, fill=badge_bg)
    draw.text((360, 1475), badge_text, fill=(240, 245, 255, 255))

    return img


def main() -> None:
    """Entrypoint for generating the 5 Miku core sprites."""
    output_dir = Path("app/resources/characters/miku_nakano/assets/core")
    output_dir.mkdir(parents=True, exist_ok=True)

    configs = [
        ("idle_neutral.webp", "idle / neutral", {"smile": False, "blush": False, "pout": False}),
        ("happy.webp", "speaking / happy", {"smile": True, "open_mouth": True, "sparkle": True}),
        ("pout.webp", "idle / pout", {"pout": True, "blush": False}),
        ("blush_shy.webp", "speaking / shy", {"blush": True, "smile": True, "open_mouth": False}),
        ("comforting.webp", "speaking / comforting", {"smile": True, "sparkle": True, "blush": False}),
    ]

    for filename, label, params in configs:
        target = output_dir / filename
        sprite = draw_miku_sprite(label, **params)
        sprite.save(target, format="WEBP", lossless=False, quality=92, method=6)
        print(f"Generated {target.resolve()} (Size: {target.stat().st_size} bytes, Mode: {sprite.mode})")


if __name__ == "__main__":
    main()
