from os.path import dirname, join
from random import randint

from PIL.Image import new
from PIL import ImageDraw, ImageFont


ttf_path = join(dirname(__file__), 'ttf', 'Vera.ttf')
bg = 0x33, 0x66, 0x99
white = 0xff, 0xff, 0xff


def new_background(size, color, bs=20, boxes=50):
    im = new('RGB', size, color=color)
    d = ImageDraw.Draw(im)
    for unused in range(boxes):
        x0 = randint(0, size[0] - bs)
        y0 = randint(0, size[1] - bs)
        c = tuple(randint(v - 10, v + 10) for v in color)
        d.rectangle((x0, y0, x0 + bs, y0 + bs), fill=c)
    return im


def front_image(name, version):
    font = ImageFont.truetype(ttf_path, 20)
    im = new_background((164, 314), bg)
    d = ImageDraw.Draw(im)
    d.text((20, 100), name, fill=white, font=font)
    d.text((20, 130), version, fill=white, font=font)
    return im


def header_image(name):
    font = ImageFont.truetype(ttf_path, 20)
    im = new_background((150, 57), bg)
    d = ImageDraw.Draw(im)
    d.text((20, 15), name, fill=white, font=font)
    return im


def icon_image(name):
    font = ImageFont.truetype(ttf_path, 200)
    im = new_background((256, 256), bg)
    d = ImageDraw.Draw(im)
    d.text((60, 20), name[0], fill=white, font=font)
    return im


if __name__ == '__main__':
    #x = front_image('test', '0.3.1')
    #x = header_image('test')
    x = icon_image('Test')
    x.save('logo.ico')
