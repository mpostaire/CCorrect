from tests.gdb_values.test_values import TestValues
from tests.gdb_values.test_functions import TestFunctions, TestFunctionTimeout
import subprocess
import os

p = subprocess.run(["make", "-C", os.path.dirname(__file__)])
if p.returncode != 0:
    exit(1)
