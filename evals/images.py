"""Renders the image recipes used by the photo-quality and vision suites. Synthetic scenes, not real photos."""
import io

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from app import verify

BRAND, OTHER, LOOKALIKE = "Sunbrew coffee", "Other Co", "Sunbrewer cafe"


def render(recipe, brand=BRAND):
    slot = recipe.get("slot", "menu")
    scen = recipe.get("scenario", "good")
    label_brand = LOOKALIKE if recipe.get("similar_brand") else brand
    img = Image.open(io.BytesIO(verify.sample_image("good" if scen == "wrong_brand" else scen, slot if slot != "table" else "menu",
                                                    OTHER if scen == "wrong_brand" else label_brand))).convert("RGB")
    d = ImageDraw.Draw(img)
    if recipe.get("blur"):
        img = img.filter(ImageFilter.GaussianBlur(recipe["blur"]))
    if recipe.get("dark"):
        img = ImageEnhance.Brightness(img).enhance(recipe["dark"])
    if recipe.get("overexposed"):
        img = ImageEnhance.Brightness(img).enhance(4.0)
    if recipe.get("noise"):
        import random
        rnd = random.Random(7)
        px = img.load()
        for _ in range(img.width * img.height // 6):
            x, y = rnd.randrange(img.width), rnd.randrange(img.height)
            r, g, b = px[x, y]
            n = rnd.randint(-recipe["noise"], recipe["noise"])
            px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))
    if recipe.get("occlude"):
        d = ImageDraw.Draw(img)
        w = int(img.width * recipe["occlude"])
        d.rectangle([img.width // 2 - w // 2, 0, img.width // 2 + w // 2, 470], fill=(70, 52, 44))
    if recipe.get("inject"):
        d = ImageDraw.Draw(img)
        d.rectangle([40, 720, img.width - 40, 790], fill=(255, 255, 255))
        d.text((60, 740), recipe["inject"], fill=(0, 0, 0), font=verify._font(26))
    if recipe.get("solid"):
        img = Image.new("RGB", img.size, (128, 128, 128))
        ImageDraw.Draw(img).line([0, 0, img.width, img.height], fill=(0, 0, 0), width=2)
        img = img.filter(ImageFilter.GaussianBlur(0.1))
    if recipe.get("size"):
        img = img.resize(tuple(recipe["size"]))
    buf = io.BytesIO()
    if recipe.get("jpeg"):
        img.save(buf, "JPEG", quality=recipe["jpeg"])
        mime = "image/jpeg"
    else:
        img.save(buf, "PNG")
        mime = "image/png"
    data = buf.getvalue()
    return Image.open(io.BytesIO(data)), data, mime
