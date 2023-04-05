import os
import unittest
import gdb
from functools import wraps
from yaml import safe_dump as yaml_dump
from ccorrect import Debugger
from ccorrect._parser import FuncCallParser


_test_results = {}


class TestAssertionError(AssertionError):
    pass


class MetaTestCase(type):
    """
    Decorates all methods starting with 'test' that weren't already decorated by the 'test_metadata' decorator (https://stackoverflow.com/a/6307917).
    This is useful because only methods decorated by 'test_metadata' can save their results and this makes the use of python's unittest module easy with CCorrect.
    """
    def __new__(cls, name, bases, dict):
        for attr in dict:
            value = dict[attr]

            is_test_method = callable(value) and value.__name__.startswith("test")
            is_wrapped_by_metadata = hasattr(value, '__CCorrect_test_has_metadata')
            if is_test_method and not is_wrapped_by_metadata:
                dict[attr] = test_metadata(value)

        return type.__new__(cls, name, bases, dict)


class TestCase(unittest.TestCase, metaclass=MetaTestCase):
    longMessage = False
    failureException = TestAssertionError
    debugger = None

    def __init__(self, methodName: str = "runTest") -> None:
        if not isinstance(self.debugger, Debugger):
            raise ValueError("Invalid 'debugger' class attribute value")
        super().__init__(methodName)

    def push_info_msg(self, msg):
        if isinstance(msg, Exception):
            if msg.args[0] is None:
                return
            msg = str(msg)
        if msg != "":
            _test_results[self.__current_problem]["tests"][-1]["messages"].append(msg)

    def push_tag(self, tag):
        if tag != "":
            _test_results[self.__current_problem]["tests"][-1]["tags"].append(tag)

    def _push_output(self):
        try:
            gdb.parse_and_eval("(int) fflush(0)")
        except gdb.error:
            pass

        try:
            with open("stdout.txt", "r+") as f:
                _test_results[self.__current_problem]["tests"][-1]["stdout"] = f.read()
                f.truncate(0)
        except FileNotFoundError:
            pass

        try:
            with open("stderr.txt", "r+") as f:
                _test_results[self.__current_problem]["tests"][-1]["stderr"] = f.read()
                f.truncate(0)
        except FileNotFoundError:
            pass

    def _push_sanitizers_and_crash_logs(self, pid):
        asan_log_path = f"asan_log.{pid}"
        try:
            with open(asan_log_path, "r") as f:
                _test_results[self.__current_problem]["tests"][-1]["asan_log"] = f.read()
            os.remove(asan_log_path)
        except FileNotFoundError:
            pass

        tsan_log_path = f"tsan_log.{pid}"
        try:
            with open(tsan_log_path, "r") as f:
                _test_results[self.__current_problem]["tests"][-1]["tsan_log"] = f.read()
            os.remove(tsan_log_path)
        except FileNotFoundError:
            pass

        try:
            with open("crash_log.txt", "r") as f:
                _test_results[self.__current_problem]["tests"][-1]["crash_log"] = f.read()
            os.remove("crash_log.txt")
        except FileNotFoundError:
            pass


def test_metadata(problem=None, description=None, weight=1, timeout=0):
    assert weight >= 1
    assert timeout >= 0

    def decorator(func):
        func.__CCorrect_test_has_metadata = True

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not isinstance(self, TestCase):
                raise TypeError("The 'test_metadata' decorator can only be used on methods of instances of 'CCorrectTestCase'")

            pb = func.__name__ if problem is None else problem
            self._TestCase__current_problem = pb
            if pb not in _test_results:
                _test_results[pb] = {
                    "success": False,
                    "score": 0,
                    "tests": []
                }

            _test_results[pb]["tests"].append({
                "description": "" if description is None else description,
                "weight": weight,
                "success": False,
                "messages": [],
                "tags": []
            })

            pid = None
            try:
                pid = self.debugger.start(timeout=timeout)
                func(self, *args, **kwargs)
            except self.failureException as e:
                self.push_info_msg(e)
                raise e
            else:
                _test_results[pb]["tests"][-1]["success"] = True
            finally:
                if pid is not None:
                    self._push_output()
                    self.debugger.finish()
                    self._push_sanitizers_and_crash_logs(pid)

        return wrapper

    if callable(problem):
        # case where decorator is used without parenthesis, all args should have their default values
        func = problem
        problem = None
        return decorator(func)
    else:
        # case where decorator is used with parenthesis
        return decorator


class BanFuncTestCase(unittest.TestCase):
    longMessage = False
    ban_functions = None
    _found = []

    def test_banned(self):
        used_banned_funcs = self.__check_banned_funcs(self.ban_functions)
        BanFuncTestCase._found = used_banned_funcs
        msg = ""
        if used_banned_funcs:
            msg = f"Found banned functions: {', '.join(used_banned_funcs)}"
        self.assertIsNone(used_banned_funcs, msg)

    def __check_banned_funcs(self, banned):
        if banned is None or "functions" not in banned or "sources" not in banned:
            return None

        func_calls = set()
        for source in banned["sources"]:
            func_calls.update(FuncCallParser(source).parse())

        found = func_calls & set(banned["functions"])
        return found if found else None


def _run_ban_test(ban_functions, runner, result_filepath):
    BanFuncTestCase.ban_functions = ban_functions
    BanFuncTestCase._found = []
    ban_suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(BanFuncTestCase)])
    res = runner.run(ban_suite)
    if res.failures:
        with open(result_filepath, "w") as f:
            data = {
                "summary": {
                    "total": 1,
                    "succeeded": 0,
                    "failed": 1,
                    "score": 0,
                    "error": {
                        "reason": "banned_functions",
                        "data": BanFuncTestCase._found,
                    }
                }
            }
            yaml_dump(data=data, stream=f, sort_keys=False)
        return True
    return False


def run_tests(test_cases=None, verbosity=0, ban_functions=None, result_filepath="results.yml"):
    try:
        os.remove(result_filepath)
    except FileNotFoundError:
        pass

    _test_results.clear()

    runner = unittest.TextTestRunner(verbosity=verbosity)

    if _run_ban_test(ban_functions, runner, result_filepath):
        return

    if test_cases is None:
        unittest.main(exit=False, verbosity=verbosity)
    else:
        suite = unittest.TestSuite()
        for test_class in test_cases:
            tests = unittest.defaultTestLoader.loadTestsFromTestCase(test_class)
            suite.addTests(tests)
        runner.run(suite)

    try:
        os.remove("stdout.txt")
        os.remove("stderr.txt")
    except FileNotFoundError:
        pass

    total = sum([len(x["tests"]) for x in _test_results.values()])
    succeeded = 0
    total_score = 0
    total_sum_weights = 0
    for problem in _test_results.values():
        problem_sum_weights = 0
        problem_success = True
        for t in problem["tests"]:
            if "asan_log" in t and t["asan_log"]:
                t["success"] = False
            problem_success = problem_success and t["success"]
            if t["success"]:
                succeeded += 1
                total_score += t["weight"]
                problem["score"] += t["weight"]

            problem_sum_weights += t["weight"]
            total_sum_weights += t["weight"]

        problem["success"] = problem_success

        if problem_sum_weights > 0:
            problem["score"] = round((problem["score"] / problem_sum_weights) * 100, 2)

    if total_sum_weights > 0:
        total_score /= total_sum_weights

    with open(result_filepath, "w") as f:
        data = {
            "summary": {
                "total": total,
                "succeeded": succeeded,
                "failed": total - succeeded,
                "score": round(total_score * 100, 2),
            },
            "problems": _test_results
        }
        yaml_dump(data=data, stream=f, sort_keys=False)
