import os
import sys
import setuptools
from setuptools.command.install import install

with open("README.md", "r") as fh:
    long_description = fh.read()

VERSION = '0.3.5'


class VerifyVersionCommand(install):
    """Custom command to verify that the git tag matches our version"""
    description = 'verify that the git tag matches our version'

    def run(self):
        tag = os.getenv('CIRCLE_TAG')

        if tag != VERSION:
            info = "Git tag: {0} does not match the version of this app: {1}".format(
                tag, VERSION
            )
            sys.exit(info)


setuptools.setup(
    name="playback-studio",
    version=VERSION,
    author="Optibus",
    author_email="eitan@optibus.com",
    description="Record your service operations in production and replay them locally at any time in a sandbox",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Optibus/playback",
    packages=setuptools.find_packages(),
    install_requires=[
        'parse==1.6.6',
        'jsonpickle==0.9.3',
        'six==1.15.0',
        'contextlib2==0.6.0'

    ],
    extras_require={'dev': [
        'mock==2.0.0',
        'rsa<=4.0; python_version < \'3\'',
        'moto==1.3.13',
        'pytest==4.6.9',
        'parameterized==0.7.0',
        'Werkzeug==0.16.1; python_version < \'3\'',
        'Flask==1.1.2',
        'flask-restplus==0.13.0',
        'pylint==2.6.0; python_version > "3.0"',
        'pylint-junit==0.3.2; python_version > "3.0"',
        'flake8==3.8.4; python_version > "3.0"',
        'flake8-formatter-junit-xml==0.0.6; python_version > "3.0"',
        'pytest-cov==2.10.1; python_version > "3.0"'
    ]},
    classifiers=[
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=2.7',
    cmdclass={
        'verify': VerifyVersionCommand,
    },
)
