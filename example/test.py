import sys

sys.path.append("../")

import ccorrect


class TestValueBuilder(ccorrect.CCorrectTestCase):
    debugger = ccorrect.Debugger("main")

    def test_1(self):
        list_ptr = self.debugger.pointer(self.debugger.pointer("node", 0))

        with self.debugger.watch(["malloc", "free"]):
            nullptr = self.debugger.pointer("void", 0)
            with self.debugger.fail("malloc", nullptr):
                push_ret = self.debugger.call("push", [list_ptr, 42])

            self.assertEqual(self.debugger.stats["malloc"].called, 1)
            self.assertEqual(self.debugger.stats["malloc"].returns[0], 0)
            self.assertEqual(push_ret, -1)

            push_ret = self.debugger.call("push", [list_ptr, 42])

            self.assertEqual(self.debugger.stats["malloc"].called, 2)
            # ensures that push() returns 0 if malloc succeeds
            self.assertGreater(self.debugger.stats["malloc"].returns[1], 0)
            self.assertEqual(push_ret, 0)

            push_ret = self.debugger.call("push", [list_ptr, 24])

            self.assertEqual(self.debugger.stats["malloc"].called, 3)
            # ensures that push() returns 0 if malloc succeeds
            self.assertGreater(self.debugger.stats["malloc"].returns[2], 0)
            self.assertEqual(push_ret, 0)

            # list_ptr['value'] is equivalent to list_ptr.dereference().dereference()['value']
            self.assertEqual(list_ptr['value'], 24)
            self.assertEqual(list_ptr['next']['value'], 42)

            pop_ret = self.debugger.call("pop", [list_ptr])

            self.assertEqual(self.debugger.stats["free"].called, 1)
            self.assertEqual(pop_ret, 24)

            pop_ret = self.debugger.call("pop", [list_ptr])

            self.assertEqual(self.debugger.stats["free"].called, 2)
            self.assertEqual(pop_ret, 42)

    def test_0(self):
        pass

ccorrect.run_tests(verbosity=2)
