import sys

from setuptools import setup, find_packages, Extension


NAME = 'dailymg'
VERSION = '0.1'
AUTHOR = 'Romuald Brunet'

TEST_REQUIRE = ['pytest', 'mock', 'freezegun']

setup(name=NAME,
      version=VERSION,
      packages=[NAME],
      package_dir={'': 'src'},
      author='Romuald Brunet',
      author_email='romuald@chivil.com',
      entry_points={'console_scripts': ['dailymg = dailymg:main']},
      setup_requires=['pytest-runner'],
      tests_require=TEST_REQUIRE,
      extras_require={'test': TEST_REQUIRE},
      classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Programming Language :: Python :: 2.7',
        ]
      )
