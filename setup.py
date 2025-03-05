#!/usr/bin/env python

from setuptools import setup

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

'''
with open('requirements.txt') as req_file:
    requirements = req_file.read().splitlines()
'''
requirements = ['networkx', 'dash_cytoscape', 'dash', 'pandas', 'matplotlib', 'filelock', 'tornado']

setup(
    author="Theo Portlock",
    author_email='zn.tportlock@gmail.com',
    python_requires='>=3.5',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    description="Run bash commands with python multiprocessing according to a tsv file edgelist.",
    entry_points={
        'console_scripts': [
            'wf=workforce.cli:main',
        ],
    },
    install_requires=requirements,
    license="MIT license",
    long_description=readme + '\n\n' + history,
    keywords='workforce',
    name='workforce',
    packages = ["workforce"],
    url='https://github.com/theoportlock/workforce',
    version='1.0.27',
)
