from setuptools import setup

setup(
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    description="werkzeug + twisted.web",
    install_requires=[
        "Twisted>=12.1",
        "werkzeug",
        "mock"
    ],
    keywords="twisted flask werkzeug web",
    license="MIT",
    name="klein",
    packages=["klein"],
    url="https://github.com/twisted/klein",
    version="0.2.2",
    maintainer='David Reid',
    maintainer_email='dreid@dreid.org',
    long_description=open('README.rst').read()
)
