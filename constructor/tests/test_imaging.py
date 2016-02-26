import shutil
import tempfile

from constructor.imaging import write_images


def test_write_images():
    tmp_dir = tempfile.mkdtemp()

    info = {'name': 'test', 'version': '0.3.1'}
    write_images(info, tmp_dir)

    shutil.rmtree(tmp_dir)


if __name__ == '__main__':
    test_write_images()
