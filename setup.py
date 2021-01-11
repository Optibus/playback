from setuptools import setup, find_packages

VERSION = "0.0.1"


setup(
    name='playback2',
    version=VERSION,
    author="Optibus",
    packages=find_packages(),
    install_requires=[
        'parse==1.6.6',
        'jsonpickle==0.9.3',
    ],
    extras_require={'dev': [
        'mock==2.0.0',
        'moto==1.3.13'
    ]},
)
