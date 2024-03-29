import ccorrect
import unittest
import os
import gdb


program = os.path.join(os.path.dirname(__file__), "main")
debugger = ccorrect.Debugger(program)


class TestFunctions(unittest.TestCase):
    def setUp(self):
        debugger.start()

    def tearDown(self):
        debugger.free_allocated_values()
        debugger.stats.clear()
        debugger.finish()

    def test_basic_call(self):
        repeat_char, str_struct_name_len = debugger.functions(["repeat_char", "str_struct_name_len"])

        char = debugger.value("char", "c")
        count = debugger.value("int", 10)
        ret = repeat_char(char, count)
        self.assertEqual(ret.string(), "c" * 10)

        value = debugger.value("str_struct", {"value": 42, "name": "Hello there"})
        ret = str_struct_name_len(debugger.pointer(value))
        self.assertEqual(ret, 11)

    def test_call_variadic(self):
        printf, fflush = debugger.functions(["printf", "fflush"])
        printf("Hello stdout %d!\n", debugger.value("char", 42))
        printf("Hello stdout %d!\n", debugger.value("int", 425494))
        printf("Hello stdout %c %d!\n", debugger.value("char", 42), debugger.value("int", 425494))

        fflush(gdb.parse_and_eval("stdout"))
        lines = debugger.get_stdout()

        self.assertEqual("Hello stdout 42!\n", lines[0])
        self.assertEqual("Hello stdout 425494!\n", lines[1])
        self.assertEqual("Hello stdout * 425494!\n", lines[2])

    def test_call_generate_arg_from_template(self):
        repeat_char, str_struct_name_len, test_struct_mean = debugger.functions(["repeat_char", "str_struct_name_len", "test_struct_mean"])

        ret = repeat_char("c", 10)
        self.assertEqual(ret.string(), "c" * 10)

        ret = str_struct_name_len({"value": 42, "name": "Hello there"})
        self.assertEqual(ret, 11)

        # test array-to-pointer decay
        test_struct_array = [{"c": 0, "i": 32}, {"c": 1, "i": 40}]
        assert test_struct_mean(test_struct_array, 2) == 36

    def test_call_return_args(self):
        return_arg = debugger.function("return_arg")
        value = debugger.pointer(debugger.pointer("test_struct", 0))
        return_arg(value, 21)
        self.assertEqual(value.dereference().dereference()["c"], 10)
        self.assertEqual(value.dereference().dereference()["i"], 42)

    def test_watch(self):
        repeat_char = debugger.function("repeat_char")

        self.assertEqual(len(debugger.stats.keys()), 0)
        repeat_char("c", 10)
        self.assertEqual(len(debugger.stats.keys()), 0)

        with debugger.watch("malloc"):
            ret = repeat_char("c", 5)
        self.assertEqual(len(debugger.stats.keys()), 1)
        self.assertEqual(debugger.stats["malloc"].called, 1)
        self.assertEqual(len(debugger.stats["malloc"].args), 1)
        self.assertEqual(len(debugger.stats["malloc"].args[0]), 1)
        self.assertEqual(debugger.stats["malloc"].args[0][0], 6)
        self.assertEqual(len(debugger.stats["malloc"].returns), 1)
        self.assertGreater(debugger.stats["malloc"].returns[0], 0)
        self.assertTrue(debugger.malloced(ret))
        self.assertEqual(debugger.allocated_size(), 6)

        repeat_char("c", 2)
        self.assertEqual(len(debugger.stats.keys()), 1)

        debugger.stats.clear()
        with debugger.watch("malloc"), debugger.watch("malloc"):
            ret = repeat_char("c", 5)
        self.assertEqual(debugger.stats["malloc"].called, 1)
        self.assertTrue(debugger.malloced(ret))
        self.assertEqual(debugger.allocated_size(), 12)

    def test_fail(self):
        repeat_char, str_struct_name_len = debugger.functions(["repeat_char", "str_struct_name_len"])

        ret = repeat_char("c", 10)
        self.assertEqual(ret.string(), "c" * 10)

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
                self.assertFalse(debugger.malloced(ret))
                self.assertEqual(debugger.allocated_size(), 0)

            ret = repeat_char("c", 10)
            self.assertEqual(ret.string(), "c" * 10)
            self.assertEqual(debugger.stats["malloc"].called, 2)
            self.assertEqual(len(debugger.stats["malloc"].args), 2)
            self.assertEqual(len(debugger.stats["malloc"].returns), 2)
            self.assertTrue(debugger.malloced(ret))
            self.assertEqual(debugger.allocated_size(), 11)

        ret = repeat_char("c", 10)
        self.assertEqual(ret.string(), "c" * 10)
        self.assertEqual(debugger.stats["malloc"].called, 2)
        self.assertEqual(len(debugger.stats["malloc"].args), 2)
        self.assertEqual(len(debugger.stats["malloc"].returns), 2)
        self.assertFalse(debugger.malloced(ret))
        self.assertEqual(debugger.allocated_size(), 11)

    def test_fail_watch(self):
        repeat_char = debugger.function("repeat_char")

        with debugger.fail("malloc", debugger.pointer("void", 0)):
            with debugger.watch("malloc"):
                ret = repeat_char("c", 10)
                self.assertEqual(ret, 0)
                self.assertEqual(debugger.stats["malloc"].called, 1)
                self.assertEqual(len(debugger.stats["malloc"].args), 1)
                self.assertEqual(len(debugger.stats["malloc"].returns), 1)
                self.assertFalse(debugger.malloced(ret))
                self.assertEqual(debugger.allocated_size(), 0)

            ret = repeat_char("c", 10)
            self.assertEqual(ret, 0)
            self.assertEqual(debugger.stats["malloc"].called, 1)
            self.assertEqual(len(debugger.stats["malloc"].args), 1)
            self.assertEqual(len(debugger.stats["malloc"].returns), 1)
            self.assertFalse(debugger.malloced(ret))
            self.assertEqual(debugger.allocated_size(), 0)

        ret = repeat_char("c", 10)
        self.assertEqual(ret.string(), "c" * 10)
        self.assertEqual(debugger.stats["malloc"].called, 1)
        self.assertEqual(len(debugger.stats["malloc"].args), 1)
        self.assertEqual(len(debugger.stats["malloc"].returns), 1)
        self.assertFalse(debugger.malloced(ret))
        self.assertEqual(debugger.allocated_size(), 0)

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
            self.assertEqual(debugger.allocated_size(), 0)

        debugger.stats.clear()
        test_free()
        self.assertEqual(len(debugger.stats.keys()), 0)

    def test_malloced_free(self):
        self.assertEqual(debugger.allocated_size(), 0)

        repeat_char, wrap_free = debugger.functions(["repeat_char", "wrap_free"])
        with debugger.watch("malloc"):
            ret = repeat_char("c", 10)
            self.assertGreater(ret, 0)
            self.assertEqual(debugger.stats["malloc"].called, 1)
            self.assertEqual(len(debugger.stats["malloc"].args), 1)
            self.assertEqual(len(debugger.stats["malloc"].returns), 1)
            self.assertEqual(debugger.allocated_size(), 11)
            self.assertTrue(debugger.malloced(ret))
            self.assertTrue(debugger.malloced(ret + 10))
            self.assertFalse(debugger.malloced(ret + 11))

        wrap_free(ret)
        self.assertTrue(debugger.malloced(ret))
        self.assertEqual(debugger.allocated_size(), 11)

        with debugger.watch(["malloc", "free"]):
            ret = repeat_char("c", 10)
            self.assertGreater(ret, 0)
            self.assertEqual(debugger.stats["malloc"].called, 2)
            self.assertEqual(len(debugger.stats["malloc"].args), 2)
            self.assertEqual(len(debugger.stats["malloc"].returns), 2)
            self.assertTrue(debugger.malloced(ret))
            self.assertEqual(debugger.allocated_size(), 22)

            wrap_free(ret)
            self.assertFalse(debugger.malloced(ret))
            self.assertEqual(debugger.allocated_size(), 11)

    def test_fail_errno(self):
        open_file_r = debugger.function("open_file_r")
        errno = gdb.parse_and_eval("&errno")

        with debugger.fail("open", retval=-1, errno=42):
            fd = open_file_r(program)
            self.assertEqual(fd, -1)
            self.assertEqual(errno.dereference(), 42)

    def test_fail_when(self):
        repeat_char = debugger.function("repeat_char")
        NULL = debugger.pointer("void", 0)

        size_count = 0
        fail_when = [0, 1, 4, 7, 4, 2]
        with debugger.watch("malloc"), debugger.fail("malloc", retval=NULL, when=fail_when):
            for i in range(10):
                ret = repeat_char("c", i)
                if i in fail_when:
                    self.assertEqual(ret, NULL)
                    self.assertFalse(debugger.malloced(size_count))
                else:
                    self.assertEqual(ret.string(), "c" * i)
                    self.assertTrue(debugger.malloced(ret))
                    size_count += i + 1
                    self.assertEqual(debugger.allocated_size(), size_count)

        self.assertEqual(debugger.stats["malloc"].called, 10)
        self.assertEqual(len(debugger.stats["malloc"].returns), 10)
        self.assertEqual(len(debugger.stats["malloc"].args), 10)
        self.assertTrue(all(args[0] == i + 1 for i, args in enumerate(debugger.stats["malloc"].args)))

        with debugger.fail("malloc", retval=NULL, when=fail_when):
            for i in range(3):
                ret = repeat_char("c", i)
                if i in fail_when:
                    self.assertEqual(ret, NULL)
                else:
                    self.assertEqual(ret.string(), "c" * i)

        for i in range(7):
            ret = repeat_char("c", i)
            self.assertEqual(ret.string(), "c" * i)

    def test_fail_return_args(self):
        test_return_arg = debugger.function("test_return_arg")

        ret = test_return_arg(2)
        self.assertEqual(ret, 4)

        with debugger.fail("return_arg", ret_args={0: {"i": 40,"c": 2}}):
            ret = test_return_arg(2)
            self.assertEqual(ret, 80)

    def test_watch_fail_return_args(self):
        test_return_arg = debugger.function("test_return_arg")

        ret = test_return_arg(2)
        self.assertEqual(ret, 4)

        with debugger.watch("return_arg"):
            with debugger.fail("return_arg", ret_args={0: {"i": 11,"c": 3}}):
                ret = test_return_arg(2)
                self.assertEqual(ret, 33)
            self.assertEqual(debugger.stats["return_arg"].called, 1)
            self.assertEqual(debugger.stats["return_arg"].returns[0], None)
            self.assertEqual(len(debugger.stats["return_arg"].args[0]), 2)
            self.assertEqual(debugger.stats["return_arg"].args[0][0]["i"], 11)
            self.assertEqual(debugger.stats["return_arg"].args[0][0]["c"], 3)
            self.assertEqual(debugger.stats["return_arg"].args[0][1], 2)


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
