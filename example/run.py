#!/bin/python3

import sys

sys.path.append("../")

import ccorrect
import subprocess

subprocess.run(["make"])
results = ccorrect.run("test.py")
print("failed" if results["summary"]["failed"] > 0 else "success")
