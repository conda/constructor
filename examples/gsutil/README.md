Based system CentOS 7.

Install miniconda:
```
DIR=/srv/miniconda
yum install -y wget bzip2 git patch vim
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh-b -p $DIR
export PATH=$DIR/bin:$PATH
```

Install constructor and conda-build:
```
conda install constructor
conda install conda-build
```

Create gsutil skeleton:
```
conda skeleton pypi gsutil
```

Build dependencies for gsutil:
```
conda skeleton pypi argcomplete --version 1.8.2; conda build argcomplete
conda skeleton pypi crcmod --version 1.7; conda build crcmod
conda skeleton pypi httplib2 --version 0.9.1; conda build httplib2
conda skeleton pypi retry_decorator --version 1.0.0; conda build retry_decorator
conda skeleton pypi socksipy-branch; conda build socksipy-branch
conda skeleton pypi rsa --version 3.1.4 ; conda build rsa
```

Build oauth2client with small fixes:
```
conda skeleton pypi oauth2client --version 2.2.0
vim oauth2client/meta.yaml
...
  imports:
    - oauth2client
    - oauth2client.contrib
    #comment this line:
    #- oauth2client.contrib.django_util

conda build oauth2client
```

Build more dependencies:
```
conda skeleton pypi gcs-oauth2-boto-plugin --version 1.14 ; conda build gcs-oauth2-boto-plugin
conda skeleton pypi unittest2 --version 0.5.1 ; conda build unittest2
conda skeleton pypi google-apitools --version 0.5.3 ; conda build google-apitools
```

Build gsutil:
```
vim gsutil/meta.yaml
  #comment this lines:
  #commands:
    #- gsutil --help

vim gsutil/build.sh
python setup.py install --single-version-externally-managed --record=/tmp/record.txt

conda build gsutil
```

Convert packages for Mac OS X and Windows:
```
cd /srv/dna_tools/miniconda-latest/conda-bld/
ls $DIR/conda-bld/linux-64/* | grep -v "repodata" | xargs -i conda convert -f --platform osx-64 {}
ls $DIR/conda-bld/linux-64/* | grep -v "repodata" | xargs -i conda convert -f --platform win-64 {}
```

Install anaconda client, login to your account and upload files to Anaconda Cloud:
```
conda install anaconda-client
anaconda login
ls $DIR/conda-bld/linux-64/* -rt1 | grep -v "repodata" | xargs -i anaconda upload {}
ls $DIR/conda-bld/osx-64/* -rt1 | grep -v "repodata" | xargs -i anaconda upload {}
ls $DIR/conda-bld/win-64/* -rt1 | grep -v "repodata" | xargs -i anaconda upload {}
```

Create construct.yaml:
```
vim construct.yaml 
name: gsutil
version: 1.0.0

channels:
  - http://repo.continuum.io/pkgs/free/
  - https://conda.anaconda.org/conda-forge
  - https://conda.anaconda.org/idna # Or your channel
specs:
  - python 2.7*
  - pycrypto 2.6.1
  - cached-property 1.3.0
  - raven 6.0.0
  - pyinstaller 3.2.1
  - google-api-python-client 1.6.2
  - gsutil 4.27
```

Build installer for Linux and Mac OS X:
```
constructor .
...
Successfully created '/gsutil-1.0.0-Linux-x86_64.sh'.

constructor . --platform=osx-64
...
Successfully created '/gsutil-1.0.0-MacOSX-x86_64.sh'.
```

Build installer for Windows:
1. Install [miniconda](https://repo.continuum.io/miniconda/Miniconda2-latest-Windows-x86_64.exe)
2. Install constructor: `conda install constructor`
3. Create meta.yaml
4. Build installer: `constructor .`

Tested on:
* CentOS 6, 7
* Ubuntu 12.04, 16.04
* Debian 7, 8
* Windows 10
* Mac OS X (not tested, if you have Mac you test it)

