# (c) 2016 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from os.path import dirname, join
from random import randint

from PIL import Image, ImageDraw, ImageFont


ttf_path = join(dirname(__file__), 'ttf', 'Vera.ttf')
welcome_size = 164, 314
header_size = 150, 57
icon_size = 256, 256
blue3 = 0x33, 0x66, 0x99
white = 0xff, 0xff, 0xff


def new_background(size, color, bs=20, boxes=50):
    im = Image.new('RGB', size, color=color)
    d = ImageDraw.Draw(im)
    for unused in range(boxes):
        x0 = randint(0, size[0] - bs)
        y0 = randint(0, size[1] - bs)
        c = tuple(randint(v - 10, v + 10) for v in color)
        d.rectangle((x0, y0, x0 + bs, y0 + bs), fill=c)
    return im


def mk_welcome_image(name, version):
    font = ImageFont.truetype(ttf_path, 20)
    im = new_background(welcome_size, blue3)
    d = ImageDraw.Draw(im)
    d.text((20, 100), name, fill=white, font=font)
    d.text((20, 130), version, fill=white, font=font)
    return im


def mk_header_image(name, unused=None):
    font = ImageFont.truetype(ttf_path, 20)
    im = Image.new('RGB', header_size, color=white)
    d = ImageDraw.Draw(im)
    d.text((20, 15), name, fill=blue3, font=font)
    return im


def mk_icon_image(name, unused=None):
    font = ImageFont.truetype(ttf_path, 200)
    im = new_background(icon_size, blue3)
    d = ImageDraw.Draw(im)
    d.text((60, 20), name[0], fill=white, font=font)
    return im


def write_images(info, dir_path):
    for tp, size, f, ext in [
        ('welcome', welcome_size, mk_welcome_image, '.bmp'),
        ('header',  header_size,  mk_header_image,  '.bmp'),
        ('icon',    icon_size,    mk_icon_image,    '.ico'),
        ]:
        key = tp + '_image'
        if key in info:
            im = Image.open(info[key])
            im = im.resize(size)
        else:
            im = f(info['name'], info['version'])
        assert im.size == size
        im.save(join(dir_path, tp + ext))
