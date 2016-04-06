import io
from setuptools import setup, find_packages

long_description = '\n'.join((
    io.open('README.rst', encoding='utf-8').read(),
    io.open('CHANGES.txt', encoding='utf-8').read()
))

setup(name='more.transaction',
      version='0.7.dev0',
      description="transaction integration for Morepath",
      long_description=long_description,
      author="Martijn Faassen",
      author_email="faassen@startifact.com",
      keywords='morepath sqlalchemy zodb transaction',
      license="BSD",
      url="http://pypi.python.org/pypi/more.transaction",
      namespace_packages=['more'],
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          'morepath >= 0.13',
          'transaction',
      ],
      extras_require=dict(
          test=[
              'coverage',
              'pytest >= 2.6.0',
              'pytest-cov',
              'webtest'
          ],
      ))
