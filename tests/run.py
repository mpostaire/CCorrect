#!/bin/python3

import sys


sys.path.insert(0, "../")

if __name__ == "__main__":
    import ccorrect
    ccorrect.run(__file__)
elif __name__ == "gdb":
    import unittest
    unittest.main("tests", verbosity=2)
