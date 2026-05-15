from setuptools import setup, find_packages

setup(
    name="qssh",
    version="0.1.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "qssh=qssh.__main__:main",
        ],
    },
    python_requires=">=3.10",
    install_requires=[
        "pexpect; sys_platform!='win32'",
    ],
)
