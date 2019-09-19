from ..shar import create_writeable_tmpdir

import tempfile
from os.path import join
from os import makedirs
from unittest.mock import patch
from psutil._common import sdiskpart
from shutil import rmtree


def test_create_tmpfile():
    install_dir = join(tempfile.tempdir, "z", "y")
    tmp_dir = create_writeable_tmpdir(install_dir)
    assert tempfile.tempdir in tmp_dir
    assert install_dir not in tmp_dir
    rmtree(tmp_dir)



@patch('psutil.disk_partitions', return_value=[sdiskpart(device="/", mountpoint=tempfile.tempdir, opts="rw,noexec", fstype="apfs")])
def test_create_tmpfile_noexec(psutil):
    install_dir = join(tempfile.tempdir, "z")
    makedirs(install_dir)
    tmp_dir = create_writeable_tmpdir(install_dir)
    assert install_dir in tmp_dir
    rmtree(tmp_dir)
    rmtree(install_dir)