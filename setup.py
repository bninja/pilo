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
    ],
    package_data={'': ['LICENSE']},
    include_package_data=True,
    tests_require=[
        'nose >=1.1.0',
        'mock ==0.8',
        'unittest2 >=0.5.1',
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
