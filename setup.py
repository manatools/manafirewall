#!/usr/bin/env python3

from setuptools import setup
exec(open('manafirewall/version.py').read())

try:
  import yui
except ImportError:
  import sys
  print('Please install python3-yui in order to install this package',
        file=sys.stderr)
  sys.exit(1)


setup(
  name=__project_name__,
  version=__project_version__,
  author='Angelo Naselli',
  author_email='anaselli@linux.it',
  packages=["manafirewall"],
  scripts=['scripts/manafirewall'],
  license='GPLv2+',
  description='ManaTools firewalld configuration tool.',
  long_description=open('README.md').read(),
  #data_files=[('conf/manatools', ['XXX.yy',]), ],
  install_requires=[
    #"argparse",
    "distribute",
    "PyYAML",
  ],
)
