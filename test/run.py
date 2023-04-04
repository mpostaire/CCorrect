#! /bin/python3

import sys

sys.path.insert(0, "../")

import ccorrect
import subprocess

subprocess.run(["make"])
ccorrect.run("test.py")
