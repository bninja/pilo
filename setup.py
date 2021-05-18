import codecs
import os
import setuptools


with codecs.open(
    os.path.join(os.path.dirname(__file__), 'pilo', 'version.txt'),
    mode='rb',
    encoding='utf8',
) as _version_file:
    __version__ = _version_file.read().strip()


install_requires = [
    'six >=1.16',
]

tests_require = [
    'pytest',
    'pytest-cov',
    'mock',
    'iso8601',
]

packages = setuptools.find_packages('.', exclude=('tests', 'tests.*'))

setuptools.setup(
    name='pilo',
    version=__version__,
    url='https://github.com/bninja/pilo/',
    license=open('LICENSE').read(),
    author='egon',
    author_email='egon@gb.com',
    description='Yet another form parser.',
    long_description=open('README.rst').read(),
    packages=packages,
    package_data={str('pilo'): [str('version.txt')]},
    zip_safe=False,
    install_requires=install_requires,
    tests_require=tests_require,
    extras_require={
        'testing': tests_require
    },
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: ISC License (ISCL)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.5',
    ],
)
