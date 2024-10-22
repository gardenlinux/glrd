from setuptools import setup, find_packages

def read_requirements(file):
    with open(file) as f:
        return f.read().splitlines()

def read_file(file):
   with open(file) as f:
        return f.read()

long_description = read_file("README.md")
version = read_file("VERSION")
requirements = read_requirements("requirements.txt")

setup(
    name="glrd",
    author = 'Garden Linux Maintainers',
    description = 'Garden Linux Release Database',
    long_description = long_description,
    license = "MIT license",
    packages=find_packages(),
    scripts = [
        'bin/glrd',
        'bin/glrd-manage'
    ],
    install_requires = requirements,
)
