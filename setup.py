from setuptools import setup

setup(
    name="klein",
    version="0.1.0",
    description="werkzeug + twisted.web",
    packages=["klein"],
    install_requires=["Twisted", "werkzeug", "mock"]
)
