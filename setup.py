from setuptools import setup, find_packages, Extension

NAME = 'dailymg'
VERSION = '0.1'
AUTHOR = 'Romuald Brunet'


setup(name=NAME,
      version=VERSION,
      author='Romuald Brunet',
      author_email='romuald@chivil.com',
      entry_points={'console_scripts': ['dailymg = dailymg:main']},
      classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Programming Language :: Python :: 2.7',
        ]
      )
