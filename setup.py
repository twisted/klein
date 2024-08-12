from setuptools import setup


if __name__ == "__main__":
    with open("README.rst") as f:
        long_description = f.read()

    setup(
        classifiers=[
            "Environment :: Web Environment",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
            "Programming Language :: Python",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8",
            "Programming Language :: Python :: 3.9",
            "Programming Language :: Python :: 3.10",
            "Programming Language :: Python :: 3.11",
            "Programming Language :: Python :: Implementation :: CPython",
            "Programming Language :: Python :: Implementation :: PyPy",
            "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
            "Topic :: Software Development :: Libraries :: Python Modules",
        ],
        description="werkzeug + twisted.web",
        long_description=long_description,
        long_description_content_type="text/x-rst",
        python_requires=">=3.7",
        setup_requires=["incremental"],
        use_incremental=True,
        install_requires=[
            "attrs>=20.1.0",
            "hyperlink",
            "incremental",
            "Tubes",
            "Twisted>=16.6",  # 16.6 introduces ensureDeferred
            "typing_extensions ; python_version<'3.10'",
            "Werkzeug",
            "zope.interface",
        ],
        keywords="twisted flask werkzeug web",
        license="MIT",
        name="klein",
        packages=["klein", "klein.storage", "klein.test"],
        package_dir={"": "src"},
        package_data=dict(
            klein=["py.typed"],
        ),
        url="https://github.com/twisted/klein",
        maintainer="Twisted Matrix Laboratories",
        maintainer_email="twisted@python.org",
        zip_safe=False,
    )
