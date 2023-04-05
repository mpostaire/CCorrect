from tests.example_exercise.test import TestCCorrectTestCase

import subprocess
import os

subprocess.run(["make", "-C", os.path.dirname(__file__)])

