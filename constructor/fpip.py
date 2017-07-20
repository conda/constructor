# (c) 2016 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.
"""
fpip (fetch pip packages) module
"""

import os
import pip
from os.path import isdir, join

requirements_name = 'requirements.txt'


def fetch(info, verbose=True):
    download_dir = info['_pip_download_dir']
    if not isdir(download_dir):
        os.makedirs(download_dir)

    specs = info['pip']
    if verbose:
        print("pip specs: %r" % specs)

    # Generate the requirements file
    requirements_path = join(download_dir, requirements_name)
    with open(requirements_path) as requirements:
        requirements.write('\n'.join(specs))
        requirements.close()
    # execute pip from within python
    pip_cmd = ['download',
               '--disable-pip-version-check',
               '-d', download_dir,
               '-r', requirements_path]

    if verbose:
        print("Running pip module with arguments: ", pip_cmd)
    pip.main(pip_cmd)


def main(info, verbose=True):
    if 'pip' in info:
        fetch(info, verbose)

