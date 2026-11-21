"""Build code-drawn installer artwork; no external fonts or user images shipped."""
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'assets'


def generate(version: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    accent = '#00E5FF'
    icon = Image.new('RGBA', (256, 256), '#081322')
    draw = ImageDraw.Draw(icon)
    draw.line([(128, 26), (230, 128), (128, 230), (26, 128), (128, 26)], fill=accent, width=12)
    draw.ellipse((87, 87, 169, 169), outline='white', width=5)
    draw.arc((95, 88, 121, 168), -90, 90, fill=accent, width=4)
    draw.arc((135, 88, 161, 168), 90, 270, fill=accent, width=4)
    icon.save(OUT / 'app.ico', sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    hero = Image.new('RGB', (704, 1068), '#081322')
    d = ImageDraw.Draw(hero)
    for x in range(0, 704, 48):
        d.line((x, 0, x, 1068), fill='#102637')
    for y in range(0, 1068, 48):
        d.line((0, y, 704, y), fill='#102637')
    font_dir = Path('C:/Windows/Fonts')
    def font(size, bold=False):
        return ImageFont.truetype(str(font_dir / ('segoeuib.ttf' if bold else 'segoeui.ttf')), size)
    d.text((48, 62), 'DUGOUT', font=font(66, True), fill='white')
    d.text((48, 144), 'ATLAS', font=font(66, True), fill=accent)
    d.text((52, 256), f'v{version}  /  WINDOWS', font=font(25), fill='#98B4C5')
    hero.paste(icon.convert('RGB').resize((320, 320)), (192, 364))
    d.line((48, 804, 656, 804), fill=accent, width=2)
    d.text((48, 846), 'BASEBALL. IN FOCUS.', font=font(30, True), fill='white')
    d.text((48, 904), 'Players / Compare / Season Race', font=font(24), fill='#98B4C5')
    d.text((48, 996), '01   OPTIONS     02   INSTALL     03   READY', font=font(19), fill=accent)
    hero.save(OUT / 'hero.bmp')


if __name__ == '__main__':
    generate(sys.argv[1] if len(sys.argv) > 1 else '1.9')
