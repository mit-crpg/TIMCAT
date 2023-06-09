from setuptools import setup, find_packages

setup(
    name="TIMCAT",
    version="0.1.0",
    description="TIMCAT is used to capital costs of nuclear power plants",
    url="https://github.com/mit-crpg/TIMCAT",
    author="",
    author_email="",
    license="NONE",
    packages=find_packages(),
    install_requires=[
        "numpy",
        "pandas",
        "scipy",
        "matplotlib",
        "openpyxl==3.1.0",
        "pytest",
        "m2r2",
        "tqdm",
        "rich",
        "bottleneck",
        "astropy",
        "pint",
    ],
    entry_points={"console_scripts": ["timechecker = TIMCAT.main:main"]},
    classifiers=[
        "Development Status :: Concept",
        "Intended Audience :: Science/Research",
        "License :: NONE :: NONE",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.9",
    ],
)
