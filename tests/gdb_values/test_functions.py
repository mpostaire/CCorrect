import ccorrect
import unittest
import os
import gdb


program = os.path.join(os.path.dirname(__file__), "main")
debugger = ccorrect.Debugger(program, save_output=False)


class TestFunctions(unittest.TestCase):
    def setUp(self):
        debugger.start()

    def tearDown(self):
        debugger.free_allocated_values()
        debugger.stats.clear()
        debugger.finish()

    def test_basic_call(self):
        # TODO test return value as argument
        repeat_char, str_struct_name_len = debugger.functions(["repeat_char", "str_struct_name_len"])

        char = debugger.value("char", "c")
        count = debugger.value("int", 10)
        ret = repeat_char(char, count)
        self.assertEqual(ret.string(), "c" * 10)

        value = debugger.value_allocated("str_struct", {"value": 42, "name": "Hello there"})
        ret = str_struct_name_len(value)
        self.assertEqual(ret, 11)

    def test_call_generate_arg_from_template(self):
        repeat_char, str_struct_name_len = debugger.functions(["repeat_char", "str_struct_name_len"])

        ret = repeat_char("c", 10)
        self.assertEqual(ret.string(), "c" * 10)

        ret = str_struct_name_len({"value": 42, "name": "Hello there"})
        self.assertEqual(ret, 11)

    def test_watch(self):
        repeat_char = debugger.function("repeat_char")

        self.assertEqual(len(debugger.stats.keys()), 0)
        repeat_char("c", 10)
        self.assertEqual(len(debugger.stats.keys()), 0)

        with debugger.watch("malloc"):
            repeat_char("c", 5)
        self.assertEqual(len(debugger.stats.keys()), 1)
        self.assertEqual(debugger.stats["malloc"].called, 1)
        self.assertEqual(len(debugger.stats["malloc"].args), 1)
        self.assertEqual(len(debugger.stats["malloc"].args[0]), 1)
        self.assertEqual(debugger.stats["malloc"].args[0][0], 6)
        self.assertEqual(len(debugger.stats["malloc"].returns), 1)
        self.assertGreater(debugger.stats["malloc"].returns[0], 0)

        repeat_char("c", 2)
        self.assertEqual(len(debugger.stats.keys()), 1)

        debugger.stats.clear()
        with debugger.watch("malloc"), debugger.watch("malloc"):
            repeat_char("c", 5)
        self.assertEqual(debugger.stats["malloc"].called, 1)

    def test_fail(self):
        repeat_char, str_struct_name_len = debugger.functions(["repeat_char", "str_struct_name_len"])

        ret = repeat_char("c", 10)
        self.assertEqual(ret.string(), "c" * 10)

        # TODO fail retval and errno from template

        NULL = debugger.pointer("void", 0)
        with debugger.fail("malloc", NULL):
            ret = repeat_char("c", 10)
        self.assertEqual(ret, 0)
        # this should not record stats on malloc as it was not explicitely told to
        self.assertEqual(len(debugger.stats.keys()), 0)

        # test with multiple fail (the last fail call in the scope should be the one that works):
        with debugger.fail("strlen", debugger.value("int", 0)):
            ret = str_struct_name_len({"value": 42, "name": "Hello there"})
            self.assertEqual(ret, 0)
            self.assertEqual(len(debugger.stats.keys()), 0)

            with debugger.fail("strlen", debugger.value("int", 1)):
                ret = str_struct_name_len({"value": 42, "name": "Hello there"})
                self.assertEqual(ret, 1)
                self.assertEqual(len(debugger.stats.keys()), 0)

            ret = str_struct_name_len({"value": 42, "name": "Hello there"})
            self.assertEqual(ret, 0)
            self.assertEqual(len(debugger.stats.keys()), 0)

    def test_watch_fail(self):
        repeat_char = debugger.function("repeat_char")

        with debugger.watch("malloc"):
            with debugger.fail("malloc", debugger.pointer("void", 0)):
                ret = repeat_char("c", 10)
                self.assertEqual(ret, 0)
                self.assertEqual(debugger.stats["malloc"].called, 1)
                self.assertEqual(len(debugger.stats["malloc"].args), 1)
                self.assertEqual(len(debugger.stats["malloc"].returns), 1)

            ret = repeat_char("c", 10)
            self.assertEqual(ret.string(), "c" * 10)
            self.assertEqual(debugger.stats["malloc"].called, 2)
            self.assertEqual(len(debugger.stats["malloc"].args), 2)
            self.assertEqual(len(debugger.stats["malloc"].returns), 2)

        ret = repeat_char("c", 10)
        self.assertEqual(ret.string(), "c" * 10)
        self.assertEqual(debugger.stats["malloc"].called, 2)
        self.assertEqual(len(debugger.stats["malloc"].args), 2)
        self.assertEqual(len(debugger.stats["malloc"].returns), 2)

    def test_fail_watch(self):
        repeat_char = debugger.function("repeat_char")

        with debugger.fail("malloc", debugger.pointer("void", 0)):
            with debugger.watch("malloc"):
                ret = repeat_char("c", 10)
                self.assertEqual(ret, 0)
                self.assertEqual(debugger.stats["malloc"].called, 1)
                self.assertEqual(len(debugger.stats["malloc"].args), 1)
                self.assertEqual(len(debugger.stats["malloc"].returns), 1)

            ret = repeat_char("c", 10)
            self.assertEqual(ret, 0)
            self.assertEqual(debugger.stats["malloc"].called, 1)
            self.assertEqual(len(debugger.stats["malloc"].args), 1)
            self.assertEqual(len(debugger.stats["malloc"].returns), 1)

        ret = repeat_char("c", 10)
        self.assertEqual(ret.string(), "c" * 10)
        self.assertEqual(debugger.stats["malloc"].called, 1)
        self.assertEqual(len(debugger.stats["malloc"].args), 1)
        self.assertEqual(len(debugger.stats["malloc"].returns), 1)

    def test_watch_free(self):
        test_free = debugger.function("test_free")

        test_free()
        self.assertEqual(len(debugger.stats.keys()), 0)

        with debugger.watch("free"):
            test_free()
            self.assertEqual(debugger.stats["free"].called, 1)
            self.assertEqual(len(debugger.stats["free"].args), 1)
            self.assertEqual(len(debugger.stats["free"].args[0]), 1)
            self.assertGreater(debugger.stats["free"].args[0][0], 0)

        debugger.stats.clear()
        test_free()
        self.assertEqual(len(debugger.stats.keys()), 0)


class TestFunctionTimeout(unittest.TestCase):
    def setUp(self):
        debugger.start(timeout=1)

    def tearDown(self):
        debugger.free_allocated_values()
        debugger.stats.clear()
        debugger.finish()

    def test_timeout(self):
        repeat_char, loop = debugger.functions(["repeat_char", "loop"])

        ret = repeat_char("c", 10)
        self.assertEqual(ret.string(), "c" * 10)

        with self.assertRaises(gdb.error):
            loop()
