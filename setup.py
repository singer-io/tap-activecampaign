#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='tap-activecampaign',
      version='0.3.1',
      description='Singer.io tap for extracting data from the Google Search Console API',
      author='jeff.huth@bytecode.io',
      classifiers=['Programming Language :: Python :: 3 :: Only'],
      py_modules=['tap_activecampaign'],
      install_requires=[
          'backoff==1.8.0',
          'requests==2.23.0',
          'pyhumps==1.3.1',
          'singer-python==5.12.2'
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
              'pylint',
              'nose',
          ]
      })
