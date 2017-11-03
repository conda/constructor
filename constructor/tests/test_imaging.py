import shutil
import tempfile

from ..imaging import write_images


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
