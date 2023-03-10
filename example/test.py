import sys

sys.path.append("../")

import ccorrect
import ccorrect.testing as ctest


class TestValueBuilder(ctest.CCorrectTestCase):
    tester = ccorrect.Debugger("main", source_files=["list.c"])

    def test_1(self):
        list_ptr = self.tester.pointer(self.tester.pointer("node", 0))

        nullptr = self.tester.pointer("void", 0)
        self.tester.fail("malloc", nullptr)

        push_ret = self.tester.call("push", [list_ptr, 42])

        self.tester.stop_fail("malloc")

        self.assertEqual(self.tester.stats["malloc"].called, 1)
        self.assertEqual(self.tester.stats["malloc"].returns[0], 0)
        self.assertEqual(push_ret, -1)

        push_ret = self.tester.call("push", [list_ptr, 42])

        self.assertEqual(self.tester.stats["malloc"].called, 2)
        # ensures that push() returns 0 if malloc succeeds
        self.assertGreater(self.tester.stats["malloc"].returns[1], 0)
        self.assertEqual(push_ret, 0)

        push_ret = self.tester.call("push", [list_ptr, 24])

        self.assertEqual(self.tester.stats["malloc"].called, 3)
        # ensures that push() returns 0 if malloc succeeds
        self.assertGreater(self.tester.stats["malloc"].returns[2], 0)
        self.assertEqual(push_ret, 0)

        # list_ptr['value'] is equivalent to list_ptr.dereference().dereference()['value']
        self.assertEqual(list_ptr['value'], 24)
        self.assertEqual(list_ptr['next']['value'], 42)

        pop_ret = self.tester.call("pop", [list_ptr])

        self.assertEqual(self.tester.stats["free"].called, 1)
        self.assertEqual(pop_ret, 24)

        pop_ret = self.tester.call("pop", [list_ptr])

        self.assertEqual(self.tester.stats["free"].called, 2)
        self.assertEqual(pop_ret, 42)


ctest.run_tests()
