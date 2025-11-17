"""Setup-Konfiguration für das Flux Paket."""

from setuptools import setup, find_packages
import os

# Read README for long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="flux-artnet",
    version="1.0.0",
    author="cromm",
    author_email="your.email@example.com",
    description="Flux - Video-to-Art-Net DMX Control System with GIF support and Web Interface",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/py_artnet",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    package_data={
        "": [
            "static/*.html",
            "static/*.js",
            "static/*.css",
            "static/bootstrap-icons/**/*",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Multimedia :: Video",
        "Topic :: System :: Hardware",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "flux=main:main",
        ],
    },
    keywords="artnet dmx video gif led control flask opencv",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/py_artnet/issues",
        "Source": "https://github.com/yourusername/py_artnet",
        "Documentation": "https://github.com/yourusername/py_artnet/tree/main/docs",
    },
)
