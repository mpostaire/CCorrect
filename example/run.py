#! /bin/python3

import sys

sys.path.append("../")

import ccorrect
import subprocess

subprocess.run(["make"])
ccorrect.run("test.py")
