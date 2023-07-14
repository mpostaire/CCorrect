from setuptools import setup


setup(
    name="CCorrect",
    version="0.3.dev1",
    description="A python module to write, grade and provide feedback for exercices in C using gdb.",
    url="https://github.com/mpostaire/CCorrect",
    author="Maxime Postaire",
    license="GPL-3.0",
    packages=["ccorrect"],
    include_package_data=True,
    install_requires=["pycparser>=2.21", "PyYAML>=6.0"]
)
