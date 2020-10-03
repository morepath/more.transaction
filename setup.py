import io
from setuptools import setup, find_packages

long_description = '\n'.join((
    io.open('README.rst', encoding='utf-8').read(),
    io.open('CHANGES.txt', encoding='utf-8').read()
))

setup(
    name='more.transaction',
    version='0.9.dev0',
    description="transaction integration for Morepath",
    long_description=long_description,
    author="Martijn Faassen",
    author_email="faassen@startifact.com",
    keywords='morepath sqlalchemy zodb transaction',
    license="BSD",
    url="https://github.com/morepath/more.transaction",
    namespace_packages=['more'],
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Environment :: Web Environment',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Topic :: Internet :: WWW/HTTP :: WSGI',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Development Status :: 5 - Production/Stable'
    ],
    install_requires=[
        'setuptools',
        'morepath >= 0.15',
        'transaction >= 2.4.0',
    ],
    extras_require=dict(
        test=["pytest >= 2.9.0", "WebTest >= 2.0.14", "pytest-remove-stale-bytecode"],
        pep8=["flake8", "black"],
        coverage=["pytest-cov"],
    ),
)
