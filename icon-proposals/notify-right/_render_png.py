from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent
BG, INK, ACCENT, DARK = "#eef6f1", "#1f5c42", "#3d9a6e", "#163d2c"
SIZE = 192


def base():
    im = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, 191, 191), radius=40, fill=BG)
    return im, d


def render_bin():
    im, d = base()
    d.rounded_rectangle((48, 54, 144, 72), radius=6, fill=INK)
    d.rounded_rectangle((84, 44, 108, 58), radius=5, fill=INK)
    d.polygon([(56, 78), (136, 78), (128, 158), (64, 158)], fill=INK)
    d.rounded_rectangle((64, 146, 128, 162), radius=8, fill=INK)
    panel = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    pd.rounded_rectangle((78, 96, 114, 136), radius=6, fill=(238, 246, 241, 90))
    im = Image.alpha_composite(im, panel)
    d = ImageDraw.Draw(im)
    d.ellipse((66, 150, 82, 166), fill=INK)
    d.ellipse((110, 150, 126, 166), fill=INK)
    d.ellipse((71, 155, 77, 161), fill=BG)
    d.ellipse((115, 155, 121, 161), fill=BG)
    im.convert("RGB").save(OUT / "01-cassonetto.png", optimize=True)


def render_calendar():
    im, d = base()
    d.rounded_rectangle((44, 52, 148, 160), radius=14, fill=INK)
    d.rounded_rectangle((44, 52, 148, 80), radius=14, fill=DARK)
    d.rectangle((44, 66, 148, 80), fill=DARK)
    for x in (68, 112):
        d.rounded_rectangle((x, 40, x + 12, 68), radius=6, fill=INK)
        d.rounded_rectangle((x, 40, x + 12, 54), radius=6, fill=ACCENT)
    cells = [(58, 92), (85, 92), (112, 92), (58, 116), (112, 116)]
    panel = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    for x, y in cells:
        pd.rounded_rectangle((x, y, x + 22, y + 18), radius=4, fill=(238, 246, 241, 90))
    im = Image.alpha_composite(im, panel)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((85, 116, 107, 134), radius=4, fill=BG)
    d.ellipse((92, 121, 100, 129), fill=INK)
    d.line([(128, 148), (146, 148)], fill=ACCENT, width=4)
    d.line([(140, 142), (146, 148), (140, 154)], fill=ACCENT, width=4)
    im.convert("RGB").save(OUT / "02-calendario.png", optimize=True)


def render_bell():
    im, d = base()
    # hanger ring
    d.ellipse((84, 36, 108, 60), outline=INK, width=7)
    # dome
    d.pieslice((58, 52, 134, 128), start=180, end=360, fill=INK)
    # lower body
    d.polygon([(58, 90), (134, 90), (134, 128), (58, 128)], fill=INK)
    # mouth / rim
    d.rounded_rectangle((48, 124, 144, 140), radius=8, fill=INK)
    # clapper
    d.ellipse((86, 140, 106, 160), fill=INK)
    # alert badge
    d.ellipse((118, 56, 142, 80), fill=ACCENT)
    d.ellipse((125, 63, 135, 73), fill=BG)
    im.convert("RGB").save(OUT / "03-campanella.png", optimize=True)


if __name__ == "__main__":
    render_bin()
    render_calendar()
    render_bell()
    for p in sorted(OUT.glob("*.png")) + sorted(OUT.glob("*.svg")):
        print(p.name, p.stat().st_size)
