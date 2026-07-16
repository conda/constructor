# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

"""
Utilities to generate images out of text, used in GUI installers as logo replacements.
"""

import sys
from io import BytesIO
from os.path import dirname, join
from pathlib import Path
from random import randint

from PIL import Image, ImageDraw, ImageFont

from ._schema import InstallerTypes

ttf_path = join(dirname(__file__), "ttf", "Vera.ttf")
with open(ttf_path, "rb") as f:
    ttf_bytes = f.read()
white = 0xFF, 0xFF, 0xFF
# These are for Windows
welcome_size = 164, 314
header_size = 150, 57
icon_size = 256, 256
# These are for OSX
welcome_size_osx = 1227, 600
# MSI/WiX image sizes
# WiX WelcomeDlg uses a full-background image with text overlaid on the right side.
# We create a side-panel effect: branding on left 164px, white padding on right.
welcome_size_msi = (493, 312)
welcome_side_panel_width_msi = 164  # Width for branding area (matches EXE welcome width)
header_size_msi = (493, 58)


def new_background(size, color, bs=20, boxes=50):
    im = Image.new("RGB", size, color=color)
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
    font = ImageFont.truetype(BytesIO(ttf_bytes), 20)
    im = new_background(welcome_size, info["_color"])
    text = "\n".join([info["welcome_image_text"], info["version"]])
    add_text(im, (20, 100), text, 2, 30, font, white)
    return im


def mk_welcome_image_osx(info):
    font = ImageFont.truetype(BytesIO(ttf_bytes), 40)
    # Transparent background
    im = Image.new("RGBA", welcome_size_osx, color=(0, 0, 0, 0))
    text = "\n".join([info["welcome_image_text"], info["version"]])
    add_text(im, (40, 450), text, 2, 60, font, info["_color"])
    return im


def mk_header_image(info):
    font = ImageFont.truetype(BytesIO(ttf_bytes), 20)
    im = Image.new("RGB", header_size, color=white)
    text = info["header_image_text"]
    color = info["_color"]
    add_text(im, (20, 15), text, 1, 20, font, color)
    return im


def mk_icon_image(info):
    font = ImageFont.truetype(BytesIO(ttf_bytes), 200)
    im = new_background(icon_size, info["_color"])
    d = ImageDraw.Draw(im)
    d.text((60, 20), info["name"][0], fill=white, font=font)
    return im


def add_color_info(info):
    color_map = {
        "red": (0xCC, 0x33, 0x33),
        "green": (0x33, 0x99, 0x33),
        "blue": (0x33, 0x66, 0x99),
        "yellow": (0xCC, 0xCC, 0x33),
    }
    color_name = info.get("default_image_color", "blue")
    try:
        info["_color"] = color_map[color_name]
    except KeyError:
        sys.exit("Error: color '%s' not defined" % color_name)


def _resize_for_msi_welcome(image_path):
    """Resize image for MSI welcome dialog with side-panel layout.

    WiX WelcomeDlg uses a full-background bitmap with text overlaid on the right.
    The user's image is resized to 164x312 and placed on the left, with white
    padding on the right for the dialog text.
    """
    im = Image.open(image_path)

    # Resize to side panel dimensions (164x312)
    panel_size = (welcome_side_panel_width_msi, welcome_size_msi[1])
    im = im.resize(panel_size)

    # Create white canvas (493x312) and paste image on left side
    canvas = Image.new("RGB", welcome_size_msi, color=white)
    canvas.paste(im, (0, 0))
    return canvas


def write_images(info: dict, dir_path: Path, installer_type: InstallerTypes = InstallerTypes.EXE):
    if installer_type == InstallerTypes.EXE:
        instructions = [
            ("welcome", welcome_size, mk_welcome_image, ".bmp"),
            ("header", header_size, mk_header_image, ".bmp"),
            ("icon", icon_size, mk_icon_image, ".ico"),
        ]
    elif installer_type == InstallerTypes.PKG:
        instructions = [
            ("welcome", welcome_size_osx, mk_welcome_image_osx, ".png"),
        ]
    elif installer_type == InstallerTypes.MSI:
        # MSI uses WiX defaults; user-provided images handled separately below
        instructions = []
    else:
        raise ValueError(
            f"Installer type '{installer_type}' not supported. Choose 'exe', 'pkg', or 'msi'."
        )

    for name, size, function, ext in instructions:
        key = name + "_image"
        if info.get(key):
            im = Image.open(info[key])
            im = im.resize(size)
        else:
            add_color_info(info)
            im = function(info)
        assert im.size == size
        im.save(join(dir_path, name + ext))

    # MSI: handle custom images if provided (no auto-generation)
    if installer_type == InstallerTypes.MSI:
        if info.get("welcome_image"):
            im = _resize_for_msi_welcome(info["welcome_image"])
            assert im.size == welcome_size_msi
            im.save(join(dir_path, "welcome.bmp"))
        if info.get("header_image"):
            im = Image.open(info["header_image"])
            im = im.resize(header_size_msi)
            im.save(join(dir_path, "header.bmp"))
        if info.get("icon_image"):
            im = Image.open(info["icon_image"])
            im = im.resize(icon_size)
            im.save(join(dir_path, "icon.ico"))
