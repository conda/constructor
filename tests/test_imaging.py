import shutil
import sys
import tempfile

import pytest

if sys.platform == "win32" or sys.platform == "darwin":
    from constructor.imaging import write_images


@pytest.mark.skipif(
    sys.platform != 'win32' and sys.platform != 'darwin',
    reason='imaging not available on Linux'
)
def test_write_images():
    tmp_dir = tempfile.mkdtemp()

    info = {'name': 'test', 'version': '0.3.1'}
    for key in ('welcome_image_text', 'header_image_text'):
        if key not in info:
            info[key] = info['name']

    write_images(info, tmp_dir)

    shutil.rmtree(tmp_dir)


if __name__ == '__main__':
    test_write_images()
