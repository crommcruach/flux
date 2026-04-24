"""Setup configuration for the Flux package."""

from setuptools import setup, find_packages

# Read README for long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements — strip comments and blank lines
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [
        line.split("#")[0].strip()
        for line in fh
        if line.strip() and not line.startswith("#")
    ]
    requirements = [r for r in requirements if r]

setup(
    name="flux",
    version="0.1.0",
    author="crommcruach",
    description="Flux — GPU-accelerated video-to-ArtNet DMX system with wgpu render pipeline and web UI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/crommcruach/flux",
    # Source lives in src/; main entry point is src/main.py
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    package_data={
        "": [
            # Frontend HTML pages
            "../../frontend/*.html",
            "../../frontend/css/*.css",
            "../../frontend/js/*.js",
            "../../frontend/components/*.html",
            "../../frontend/libs/**/*",
            "../../frontend/bootstrap-icons/**/*",
            # Default config shipped with the package
            "../../config.json",
            # Plugins
            "../../plugins/**/*",
        ],
    },
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Topic :: Multimedia :: Video",
        "Topic :: System :: Hardware",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
    ],
    python_requires=">=3.10",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "flux=main:main",
        ],
    },
    keywords="artnet dmx video wgpu gpu vulkan led control flask websocket",
    project_urls={
        "Bug Reports": "https://github.com/crommcruach/flux/issues",
        "Source": "https://github.com/crommcruach/flux",
        "Changelog": "https://github.com/crommcruach/flux/blob/main/CHANGELOG.md",
    },
)
