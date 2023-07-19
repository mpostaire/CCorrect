import ccorrect
import unittest
import os
from yaml import safe_load as yaml_load


class TestExampleExercise(ccorrect.TestCase):
    debugger = ccorrect.Debugger(os.path.join(os.path.dirname(__file__), "main"), asan_detect_leaks=True)

    @ccorrect.test_metadata(
        problem="list_success",
        description="testing push"
    )
    def test_push(self):
        list_ptr = self.debugger.pointer(self.debugger.pointer("node", 0))
        push, pop = self.debugger.functions(["push", "pop"])

        with self.debugger.watch("malloc"):
            nullptr = self.debugger.pointer("void", 0)
            with self.debugger.fail("malloc", nullptr):
                push_ret = push(list_ptr, 42)

            self.assertEqual(self.debugger.stats["malloc"].called, 1)
            self.assertEqual(self.debugger.stats["malloc"].returns[0], 0)
            self.assertEqual(push_ret, -1)

            push_ret = push(list_ptr, 42)

            self.assertEqual(self.debugger.stats["malloc"].called, 2)
            # ensures that push() returns 0 if malloc succeeds
            self.assertGreater(self.debugger.stats["malloc"].returns[1], 0)
            self.assertEqual(push_ret, 0)

            push_ret = push(list_ptr, 24)

            self.assertEqual(self.debugger.stats["malloc"].called, 3)
            # ensures that push() returns 0 if malloc succeeds
            self.assertGreater(self.debugger.stats["malloc"].returns[2], 0)
            self.assertEqual(push_ret, 0)

        pop(list_ptr)
        pop(list_ptr)

    @ccorrect.test_metadata(
        problem="list_success",
        description="testing pop",
        weight=2
    )
    def test_pop(self):
        list_template = {"value": 1, "next": {"value": 2, "next": None}}
        list_ptr = self.debugger.pointer(self.debugger.pointer(self.debugger.value("node", list_template)))
        pop = self.debugger.function("pop")

        with self.debugger.watch("free"):
            # list_ptr['value'] is equivalent to list_ptr.dereference().dereference()['value']
            self.assertEqual(list_ptr['value'], 1)
            self.assertEqual(list_ptr['next']['value'], 2)

            pop_ret = pop(list_ptr)

            self.assertEqual(self.debugger.stats["free"].called, 1)
            self.assertEqual(pop_ret, 1)

            pop_ret = pop(list_ptr)

            self.assertEqual(self.debugger.stats["free"].called, 2)
            self.assertEqual(pop_ret, 2)

    def test_sigfpe(self):
        sigfpe = self.debugger.function("sigfpe")
        sigfpe()

    def test_sigsegv(self):
        sigsegv = self.debugger.function("sigsegv")
        sigsegv()

    def test_double_free(self):
        double_free = self.debugger.function("double_free")
        double_free()

    def test_memleak(self):
        memleak = self.debugger.function("memleak")
        memleak()

    def test_out_of_bounds(self):
        out_of_bounds = self.debugger.function("out_of_bounds")
        out_of_bounds()


class TestCCorrectTestCase(unittest.TestCase):
    def test_ccorrecttestcase(self):
        result_file = os.path.join(os.path.dirname(__file__), "results.yml")
        ccorrect.run_tests([TestExampleExercise], result_filepath=result_file)
        with open(result_file, "r") as f:
            results = yaml_load(f)

        self.assertDictEqual(results["summary"], {"total": 7, "succeeded": 2, "failed": 5, "score": 37.5})

        expected = {
            "success": True,
            "score": 100.0,
            "tests": [
                {
                    "description": "testing pop",
                    "weight": 2,
                    "success": True,
                    "stdout": "",
                    "stderr": "",
                    "messages": [],
                    "tags": []
                },
                {
                    "description": "testing push",
                    "weight": 1,
                    "success": True,
                    "stdout": "",
                    "stderr": "",
                    "messages": [],
                    "tags": []
                }
            ]
        }
        self.assertDictEqual(results["problems"]["list_success"], expected)

        self.assertFalse(results["problems"]["test_sigfpe"]["success"])
        self.assertEqual(results["problems"]["test_sigfpe"]["score"], 0)
        self.assertIn("AddressSanitizer: FPE", results["problems"]["test_sigfpe"]["tests"][0]["asan_log"].splitlines()[1])
        self.assertEqual(results["problems"]["test_sigfpe"]["tests"][0]["crash_log"].splitlines()[0], "ERROR: Program received signal SIGFPE")

        self.assertFalse(results["problems"]["test_sigsegv"]["success"])
        self.assertEqual(results["problems"]["test_sigsegv"]["score"], 0)
        self.assertIn("AddressSanitizer: SEGV", results["problems"]["test_sigsegv"]["tests"][0]["asan_log"].splitlines()[1])
        self.assertEqual(results["problems"]["test_sigsegv"]["tests"][0]["crash_log"].splitlines()[0], "ERROR: Program received signal SIGSEGV")

        self.assertFalse(results["problems"]["test_double_free"]["success"])
        self.assertEqual(results["problems"]["test_double_free"]["score"], 0)
        self.assertIn("AddressSanitizer: attempting double-free", results["problems"]["test_double_free"]["tests"][0]["asan_log"].splitlines()[1])

        self.assertFalse(results["problems"]["test_out_of_bounds"]["success"])
        self.assertEqual(results["problems"]["test_out_of_bounds"]["score"], 0)
        self.assertIn("AddressSanitizer: stack-buffer-overflow on address", results["problems"]["test_out_of_bounds"]["tests"][0]["asan_log"].splitlines()[1])
