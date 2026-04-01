from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="subsentry",
    version="1.0.0",
    author="m3hank",
    description="Subdomain monitoring tool with Discord alerts via ProjectDiscovery's notify",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/subsentry/subsentry",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.28.0",
    ],
    entry_points={
        "console_scripts": [
            "subsentry=subsentry.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Security",
        "Topic :: Internet :: Name Service (DNS)",
    ],
)
