from tests.gdb_values.test_values import TestValues
from tests.gdb_values.test_functions import TestFunctions, TestFunctionTimeout
import subprocess
import os

subprocess.run(["make", "-C", os.path.dirname(__file__)])
