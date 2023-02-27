import sys

sys.path.append("../")

import ccorrect
import unittest


class TestValueBuilder(unittest.TestCase):
    test_report = []

    def tearDown(self):
        tester.free_allocated_values()

    def test_1(self):
        list_ptr = tester.pointer(tester.pointer("node", 0))

        nullptr = tester.pointer("void", 0)
        tester.fail("malloc", nullptr)

        push_ret = tester.call("push", [list_ptr, 42])

        tester.stop_fail("malloc")

        self.assertEqual(tester.stats["malloc"].called, 1)
        self.assertEqual(tester.stats["malloc"].returns[0], 0)
        self.assertEqual(push_ret, -1)

        push_ret = tester.call("push", [list_ptr, 42])

        self.assertEqual(tester.stats["malloc"].called, 2)
        # ensures that push() returns 0 if malloc succeeds
        self.assertGreater(tester.stats["malloc"].returns[1], 0)
        self.assertEqual(push_ret, 0)

        push_ret = tester.call("push", [list_ptr, 24])

        self.assertEqual(tester.stats["malloc"].called, 3)
        # ensures that push() returns 0 if malloc succeeds
        self.assertGreater(tester.stats["malloc"].returns[2], 0)
        self.assertEqual(push_ret, 0)

        # list_ptr['value'] is equivalent to list_ptr.dereference().dereference()['value']
        self.assertEqual(list_ptr['value'], 24)
        self.assertEqual(list_ptr['next']['value'], 42)

        pop_ret = tester.call("pop", [list_ptr])

        self.assertEqual(tester.stats["free"].called, 1)
        self.assertEqual(pop_ret, 24)

        pop_ret = tester.call("pop", [list_ptr])

        self.assertEqual(tester.stats["free"].called, 2)
        self.assertEqual(pop_ret, 42)


with ccorrect.Debugger("main", source_files=["list.c"]) as tester:
    gdb = tester.gdb()
    unittest.main()
