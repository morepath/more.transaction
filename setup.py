import os
from setuptools import setup, find_packages

setup(name='more.transaction',
      version = '0.1dev',
      description="transaction integration for Morepath",
      author="Martijn Faassen",
      author_email="faassen@startifact.com",
      license="BSD",
      namespace_packages=['more'],
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
        'setuptools',
        'morepath',
        'transaction',
        ],
      extras_require = dict(
        test=['pytest >= 2.0',
              'pytest-cov'],
        ),
      )
