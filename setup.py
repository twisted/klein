from setuptools import setup

if __name__ == "__main__":

    with open('README.rst', 'r') as f:
        long_description = f.read()

    setup(
        classifiers=[
            'Environment :: Web Environment',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: MIT License',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3.4',
            'Programming Language :: Python :: 3.5',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: 3.7',
            'Programming Language :: Python :: Implementation :: CPython',
            'Programming Language :: Python :: Implementation :: PyPy',
            'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
            'Topic :: Software Development :: Libraries :: Python Modules'
        ],
        description="werkzeug + twisted.web",
        long_description=long_description,
        setup_requires=["incremental"],
        use_incremental=True,
        install_requires=[
            "attrs",
            'enum34 ; python_version<"3.4"',
            "hyperlink",
            "incremental",
            "six",
            "Tubes",
            "Twisted>=15.5",  # 15.5 is the first version to support Py3.3+
            "typing",
            "Werkzeug",
            "zope.interface",
        ],
        keywords="twisted flask werkzeug web",
        license="MIT",
        name="klein",
        packages=["klein", "klein.storage",
                  "klein.test"],
        package_dir={"": "src"},
        package_data=dict(
            klein=[
                "test/idna-tables-properties.csv",
            ],
        ),
        url="https://github.com/twisted/klein",
        maintainer='Amber Brown (HawkOwl)',
        maintainer_email='hawkowl@twistedmatrix.com',
    )
