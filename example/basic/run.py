#!/bin/python3

import sys

sys.path.insert(0, "../")

import ccorrect
import subprocess

subprocess.run(["make"])
results = ccorrect.run("test.py", silent_gdb=False)
print("success" if results["summary"]["score"] == 100 else "failed")
