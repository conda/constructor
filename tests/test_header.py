import os

import pytest

from constructor.shar import read_header_template
from constructor.utils import preprocess
from constructor.osxpkg import OSX_DIR


@pytest.mark.parametrize('osx', [False, True])
@pytest.mark.parametrize('direct_execute_post_install', [False, True])
@pytest.mark.parametrize('direct_execute_pre_install', [False, True])
@pytest.mark.parametrize('batch_mode', [False, True])
@pytest.mark.parametrize('keep_pkgs', [False, True])
@pytest.mark.parametrize('has_conda', [False, True])
@pytest.mark.parametrize('has_license', [False, True])
@pytest.mark.parametrize('initialize_conda', [False, True])
@pytest.mark.parametrize('initialize_by_default', [False, True])
@pytest.mark.parametrize('has_post_install', [False, True])
@pytest.mark.parametrize('has_pre_install', [False, True])
@pytest.mark.parametrize('check_path_spaces', [False, True])
@pytest.mark.parametrize('arch', ['x86', 'x86_64', ' ppc64le', 's390x', 'aarch64'])
def test_linux_template_processing(
        osx, arch, has_pre_install, has_post_install, initialize_conda,
        initialize_by_default, has_license, has_conda, keep_pkgs, batch_mode,
        direct_execute_pre_install, direct_execute_post_install, check_path_spaces):
    template = read_header_template()
    processed = preprocess(template, {
       'has_license': has_license,
       'osx': osx,
       'batch_mode': batch_mode,
       'keep_pkgs': keep_pkgs,
       'has_conda': has_conda,
       'x86': arch == 'x86',
       'x86_64': arch == 'x86_64',
       'ppc64le': arch == 'ppc64le',
       's390x': arch == 's390x',
       'aarch64': arch == 'aarch64',
       'linux': not osx,
       'has_pre_install': has_pre_install,
       'direct_execute_pre_install': direct_execute_pre_install,
       'has_post_install': has_post_install,
       'direct_execute_post_install': direct_execute_post_install,
       'initialize_conda': initialize_conda,
       'initialize_by_default': initialize_by_default,
       'check_path_spaces': check_path_spaces,

    })
    assert '#if' not in processed
    assert '#else' not in processed
    assert '#endif' not in processed


@pytest.mark.parametrize("arch", ["x86_64", "arm64"])
@pytest.mark.parametrize("check_path_spaces", [False, True])
@pytest.mark.parametrize(
    "script", 
    [
        "checks_before_install.sh", 
        "prepare_installation.sh", 
        "run_installation.sh", 
        "update_path.sh", 
        "clean_cache.sh",
        "run_user_script.sh",
    ]
)
def test_osxpkg_template_processing(arch, check_path_spaces, script):
    with open(os.path.join(OSX_DIR, script)) as f:
        data = f.read()
    processed = preprocess(data, {"arch": arch, "check_path_spaces": check_path_spaces})
    assert "#if" not in processed
    assert "#else" not in processed
    assert "#endif" not in processed