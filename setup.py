import re
import setuptools

setuptools.setup(
    name='pilo',
    version=(
        re
        .compile(r".*__version__ = '(.*?)'", re.S)
        .match(open('pilo/__init__.py').read())
        .group(1)
    ),
    url='https://github.com/bninja/pilo/',
    license=open('LICENSE').read(),
    author='egon',
    author_email='egon@gb.com',
    description='Yet another form parser.',
    long_description=open('README.rst').read(),
    packages=[
        'pilo',
        'pilo.source',
    ],
    package_data={'': ['LICENSE']},
    include_package_data=True,
    tests_require=[
        'nose >=1.0,<2.0',
        'mock >=1.0,<2.0',
        'unittest2 >=0.5.1,<0.6',
        'coverage',
    ],
    install_requires=[],
    test_suite='nose.collector',
    classifiers=[
        'Intended Audience :: Developers',
        'Development Status :: 4 - Beta',
        'Natural Language :: English',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: ISC License (ISCL)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
    ],
)
