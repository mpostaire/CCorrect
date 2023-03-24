import os
import unittest
import gdb
from functools import wraps
from yaml import safe_dump as yaml_dump
from ccorrect import Debugger

_test_results = {}


class MetaCCorrectTestCase(type):
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


class CCorrectTestCase(unittest.TestCase, metaclass=MetaCCorrectTestCase):
    longMessage = False
    debugger = None

    def __init__(self, methodName: str = "runTest") -> None:
        if not isinstance(self.debugger, Debugger):
            raise ValueError("Invalid 'debugger' class attribute value")
        super().__init__(methodName)

    def push_info_msg(self, msg):
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

        with open("stdout.txt", "r+") as f:
            _test_results[self.__current_problem]["tests"][-1]["stdout"] = f.read()
            f.truncate(0)
        with open("stderr.txt", "r+") as f:
            _test_results[self.__current_problem]["tests"][-1]["stderr"] = f.read()
            f.truncate(0)

    def _push_asan_logs(self, pid):
        asan_log_path = f"asan_log.{pid}"
        try:
            with open(asan_log_path, "r") as f:
                _test_results[self.__current_problem]["tests"][-1]["asan_log"] = f.read()
            os.remove(asan_log_path)
        except FileNotFoundError:
            pass


def test_metadata(problem=None, description=None, weight=1, timeout=0):
    assert weight >= 1
    assert timeout >= 0

    def decorator(func):
        func.__CCorrect_test_has_metadata = True

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not isinstance(self, CCorrectTestCase):
                raise TypeError("The 'test_metadata' decorator can only be used on methods of instances of 'CCorrectTestCase'")

            pb = func.__name__ if problem is None else problem
            self._CCorrectTestCase__current_problem = pb
            if pb not in _test_results:
                _test_results[pb] = {
                    "success": True,
                    "score": 0,
                    "tests": []
                }

            _test_results[pb]["tests"].append({
                "description": "" if description is None else description,
                "weight": weight,
                "success": True,
                "messages": [],
                "tags": []
            })

            pid = self.debugger.start(timeout=timeout)
            try:
                func(self, *args, **kwargs)
            except AssertionError as e:
                _test_results[pb]["tests"][-1]["success"] = False
                _test_results[pb]["success"] = False
                if e.args[0] is not None:
                    self.push_info_msg(str(e))
                raise e
            except Exception as e:
                # TODO handle error
                _test_results[pb]["tests"][-1]["success"] = False
                _test_results[pb]["success"] = False
                # If we push the exception as a message, it pollutes the report for the student
                # self.push_info_msg(str(e))
                raise e
            finally:
                self._push_output()
                self.debugger.finish()
                self._push_asan_logs(pid)

        return wrapper

    if callable(problem):
        # case where decorator is used without parenthesis, all args should have their default values
        func = problem
        problem = None
        return decorator(func)
    else:
        # case where decorator is used with parenthesis
        return decorator


def run_tests(verbosity=0):
    # TODO test_case_classes argument that is used to build test suites
    #      --> only allow 'CCorrectTestCase' subclasses

    try:
        os.remove("results.yml")
    except FileNotFoundError:
        pass

    _test_results.clear()
    unittest.main(exit=False, verbosity=verbosity)

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
        for t in problem["tests"]:
            if t["success"]:
                succeeded += 1
                total_score += t["weight"]
                problem["score"] += t["weight"]

            problem_sum_weights += t["weight"]
            total_sum_weights += t["weight"]

        if problem_sum_weights > 0:
            problem["score"] = round((problem["score"] / problem_sum_weights) * 100, 2)

    if total_sum_weights > 0:
        total_score /= total_sum_weights

    with open("results.yml", "w") as f:
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
