from pathlib import Path
from setuptools import setup, find_packages

VERSION = "2023.1.3"

setup(
    name="pydrawise",
    version=VERSION,
    description="Python API for interacting with Hydrawise sprinkler controllers.",
    long_description=Path("README.md").read_text(),
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    download_url="https://github.com/dknowles2/pydrawise/tarball/" + VERSION,
    keywords="hydrawise,api,iot",
    author="David Knowles",
    author_email="dknowles2@gmail.com",
    packages=find_packages(),
    python_requires=">=3.9",
    url="https://github.com/dknowles2/pydrawise",
    license="Apache License 2.0",
    install_requires=[
        "aiohttp",
        "apischema",
        "gql[aiohttp]",
        "graphql-core",
    ],
    include_package_data=True,
    zip_safe=True,
)
