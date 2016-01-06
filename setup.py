from setuptools import setup

if __name__ == "__main__":
    setup(
        classifiers=[
            'Environment :: Web Environment',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: MIT License',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2.6',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3.4',
            'Programming Language :: Python :: 3.5',
            'Programming Language :: Python :: Implementation :: CPython',
            'Programming Language :: Python :: Implementation :: PyPy',
            'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
            'Topic :: Software Development :: Libraries :: Python Modules'
        ],
        description="werkzeug + twisted.web",
        long_description=read('README.rst'),
        setup_requires=["incremental"],
        use_incremental=True,
        install_requires=[
            "Twisted>=13.2",
            "werkzeug"
        ],
        keywords="twisted flask werkzeug web",
        license="MIT",
        name="klein",
        packages=["klein", "klein.test"],
        url="https://github.com/twisted/klein",
        version=find_version('klein', '__init__.py'),
        maintainer='Amber Brown (HawkOwl)',
        maintainer_email='hawkowl@twistedmatrix.com',
    )
