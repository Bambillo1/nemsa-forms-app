from setuptools import setup, find_packages

setup(
    name="nemsa_forms",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'Flask',
        'pymongo',
        'flask-mail'
    ],
)