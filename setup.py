from setuptools import setup

with open("README.rst", "rb") as f:
    long_descr = f.read().decode('utf-8')

setup(
    name = "plexurl",
    packages = ["plexurl"],
    install_requires = ['plexapi', 'prettytable'],
    entry_points = {
        "console_scripts": ['plexurl = plexurl.plexurl:main']
        },
    version = "1.2.1",
    description = "Browse Plex from CLI. Returns transcoding streaming urls to stdout",
    long_description = long_descr,
    author = "Steven Smith",
    author_email = "stevensmith.ome@gmail.com",
    license = "MIT",
    url = "https://blha303.github.io/plexurl/",
    classifiers = [
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: System Administrators",
        "Topic :: Multimedia :: Sound/Audio"
        ]
    )
