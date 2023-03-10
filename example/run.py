#!/bin/python3

import sys

sys.path.append("../")

import ccorrect
import subprocess

subprocess.run(["make"])
results = ccorrect.run("test.py")
print("success" if results["summary"]["score"] == 100 else "failed")
