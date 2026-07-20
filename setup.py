#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='tap-activecampaign',
      version='1.6.0',
      description='Singer.io tap for extracting data from the ActiveCampaign API',
      author='jeff.huth@bytecode.io',
      classifiers=['Programming Language :: Python :: 3 :: Only'],
      py_modules=['tap_activecampaign'],
      install_requires=[
          'backoff==2.2.1',
          'pyhumps==3.8.0',
          'requests==2.34.2',
          'singer-python==6.8.0'
      ],
      entry_points='''
          [console_scripts]
          tap-activecampaign=tap_activecampaign:main
      ''',
      packages=find_packages(),
      package_data={
          'tap_activecampaign': [
              'schemas/*.json',
              'tests/*.py'
          ]
      },
      extras_require={
          'dev': [
              'ipdb',
          ],
          'test': [
              'coverage',
              'pylint',
              'pytest',
          ]
      })
