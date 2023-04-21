# (c) 2016-2020 Anaconda, Inc. / http://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import setuptools

import versioneer

setuptools.setup(
    name="constructor",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    author="Anaconda, Inc.",
    author_email="conda@anaconda.com",
    url="https://github.com/conda/constructor",
    license="BSD",
    description="create installer from conda packages",
    long_description=open("README.md").read(),
    packages=["constructor"],
    entry_points={
        "console_scripts": ["constructor = constructor.main:main"],
    },
    install_requires=[
        "conda >=4.6,<23.1.0",
        "ruamel.yaml",
        "pillow >=3.1 ; platform_system=='Windows' or platform_system=='Darwin'",
        # non-python dependency: "nsis >=3.01 ; platform_system=='Windows'",
    ],
    # We could differentiate between operating systems here but that is
    # far more trouble than it is worth
    package_data={
        "constructor": ['header.sh', 'nsis/*', 'osx/*', 'ttf/*']
    },
    python_requires=">=3.7",
)
