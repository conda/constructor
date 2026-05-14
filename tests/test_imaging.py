import os
import shutil
import sys
import tempfile

import pytest

if sys.platform == "win32" or sys.platform == "darwin":
    from PIL import Image

    from constructor.imaging import write_images


@pytest.mark.skipif(
    sys.platform != "win32" and sys.platform != "darwin",
    reason="imaging only available on Windows and MacOS",
)
def test_write_images():
    tmp_dir = tempfile.mkdtemp()

    info = {"name": "test", "version": "0.3.1"}
    for key in ("welcome_image_text", "header_image_text"):
        if key not in info:
            info[key] = info["name"]

    write_images(info, tmp_dir)

    shutil.rmtree(tmp_dir)


@pytest.mark.skipif(
    sys.platform != "win32" and sys.platform != "darwin",
    reason="imaging only available on Windows and MacOS",
)
def test_write_images_msi(tmp_path):
    """Test that write_images generates correct MSI branding images."""
    info = {"name": "test", "version": "0.3.1"}
    for key in ("welcome_image_text", "header_image_text"):
        if key not in info:
            info[key] = info["name"]

    write_images(info, str(tmp_path), installer_type="msi")

    # Verify welcome.bmp exists with correct dimensions (493x312)
    welcome_path = tmp_path / "welcome.bmp"
    assert welcome_path.exists(), "welcome.bmp not created"
    with Image.open(welcome_path) as img:
        assert img.size == (493, 312), f"welcome.bmp wrong size: {img.size}"

    # Verify header.bmp exists with correct dimensions (493x58)
    header_path = tmp_path / "header.bmp"
    assert header_path.exists(), "header.bmp not created"
    with Image.open(header_path) as img:
        assert img.size == (493, 58), f"header.bmp wrong size: {img.size}"

    # Verify icon.ico exists with correct dimensions (256x256)
    icon_path = tmp_path / "icon.ico"
    assert icon_path.exists(), "icon.ico not created"
    with Image.open(icon_path) as img:
        assert img.size == (256, 256), f"icon.ico wrong size: {img.size}"


if __name__ == "__main__":
    test_write_images()
