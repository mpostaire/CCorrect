import unittest
import os
from ccorrect._parser import FuncCallParser


class TestFunctionParser(unittest.TestCase):
    def test_parser(self):
        test_file = os.path.join(os.path.dirname(__file__), "main.c")
        funcs = FuncCallParser(test_file).parse()
        self.assertSetEqual(funcs, {"a", "b", "c", "d", "e", "f", "puts"})
