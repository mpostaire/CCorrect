from tests.example_exercise.test import TestCCorrectTestCase

import subprocess
import os

p = subprocess.run(["make", "-C", os.path.dirname(__file__)])
if p.returncode != 0:
    exit(1)
