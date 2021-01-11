import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="playback-studio",
    version="0.0.1",
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
    ],
    extras_require={'dev': [
        'mock==2.0.0',
        'moto==1.3.13'
    ]},
    classifiers=[
        "Programming Language :: Python :: 2.7",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=2.7',
)
