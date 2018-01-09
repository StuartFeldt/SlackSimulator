from setuptools import find_packages, setup

setup(
    name="SlackSimulator",
    version="1",
    description="An automated bot-run slack channel using markov chains",
    author="Stu Feldt",
    author_email="stu.feldt@gmail.com",
    platforms=["any"],
    license="MIT",
    url="https://github.com/StuartFeldt/SlackSimulator",
    packages=find_packages(),
    install_requires=[i.strip() for i in open("requirements.txt").readlines()],
)
