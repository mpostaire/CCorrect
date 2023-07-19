#!/bin/python3

import sys


sys.path.insert(0, "../")

if __name__ == "__main__":
    import ccorrect
    import os
    ccorrect.run(__file__)
    os.remove(os.path.join(os.path.dirname(__file__), "stderr.txt"))
    os.remove(os.path.join(os.path.dirname(__file__), "stdout.txt"))
elif __name__ == "gdb":
    import unittest
    unittest.main("tests", verbosity=2)
