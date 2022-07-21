# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import sys
from os.path import dirname, join
from random import randint

from PIL import Image, ImageDraw, ImageFont


ttf_path = join(dirname(__file__), 'ttf', 'Vera.ttf')
welcome_size = 164, 314
header_size = 150, 57
icon_size = 256, 256
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


def add_text(im, xy, text, min_lines, line_height, font, color):
    x, y = xy
    d = ImageDraw.Draw(im)
    lines = text.splitlines()
    text_height = len(lines) * line_height
    min_text_height = min_lines * line_height
    y = int(y * (im.height - text_height) / (im.height - min_text_height))
    for line in text.splitlines():
        d.text((x, y), line, fill=color, font=font)
        y += line_height
    return d


def mk_welcome_image(info):
    font = ImageFont.truetype(ttf_path, 20)
    im = new_background(welcome_size, info['_color'])
    text = '\n'.join([info['welcome_image_text'], info['version']])
    add_text(im, (20, 100), text, 2, 30, font, white)
    return im


def mk_header_image(info):
    font = ImageFont.truetype(ttf_path, 20)
    im = Image.new('RGB', header_size, color=white)
    text = info['header_image_text']
    color = info['_color']
    add_text(im, (20, 15), text, 1, 20, font, color)
    return im


def mk_icon_image(info):
    font = ImageFont.truetype(ttf_path, 200)
    im = new_background(icon_size, info['_color'])
    d = ImageDraw.Draw(im)
    d.text((60, 20), info['name'][0], fill=white, font=font)
    return im


def add_color_info(info):
    color_map = {
        'red': (0xcc, 0x33, 0x33),
        'green': (0x33, 0x99, 0x33),
        'blue': (0x33, 0x66, 0x99),
        'yellow': (0xcc, 0xcc, 0x33),
    }
    color_name = info.get('default_image_color', 'blue')
    try:
        info['_color'] = color_map[color_name]
    except KeyError:
        sys.exit("Error: color '%s' not defined" % color_name)


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
            add_color_info(info)
            im = f(info)
        assert im.size == size
        im.save(join(dir_path, tp + ext))


if __name__ == '__main__':
    info = {'name': 'test', 'version': '0.3.1',
            'default_image_color': 'yellow',
            'welcome_image': '../examples/miniconda/bird.png'}
    write_images(info, '.')
