from setuptools import Extension, setup

setup(
    name="rlp",
    description="Minimal verifier/runtime subset of the RLP puzzle package.",
    version="1.0.0",
    install_requires=["numpy>=2.0.0", "pygame>=2.1.0"],
    packages=["rlp"],
    package_dir={"rlp": "rlp"},
    ext_modules=[Extension("rlp.constants", ["rlp/constants/puzzle_constants.c"])],
)
