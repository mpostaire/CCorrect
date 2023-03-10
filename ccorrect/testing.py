import os
import unittest
import gdb
from functools import wraps
from yaml import safe_dump as yaml_dump
from ccorrect import Debugger

__test_reports = []


class MetaCCorrectTestCase(type):
    """
    Decorates all methods starting with 'test' that weren't already decorated by the 'test_metadata' decorator (https://stackoverflow.com/a/6307917).
    This is useful because only methods decorated by 'test_metadata' can save their results and this makes the use of python's unittest module easy with CCorrect.
    """
    def __new__(cls, name, bases, dict):
        for attr in dict:
            value = dict[attr]

            is_test_method = callable(value) and value.__name__.startswith("test")
            is_wrapped_by_metadata = hasattr(value, '__CCorrect_metadata_wrapped')
            if is_test_method and not is_wrapped_by_metadata:
                dict[attr] = test_metadata(value)

        return type.__new__(cls, name, bases, dict)


class CCorrectTestCase(unittest.TestCase, metaclass=MetaCCorrectTestCase):
    longMessage = False
    tester = None

    def __init__(self, methodName: str = "runTest") -> None:
        if not isinstance(self.tester, Debugger):
            raise ValueError("Invalid 'tester' class attribute value") 
        super().__init__(methodName)


def test_metadata(problem=None, description=None, weight=1, timeout=0):
    assert weight >= 0
    assert timeout >= 0

    def decorator(func):
        func.__CCorrect_metadata_wrapped = True

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not isinstance(self, CCorrectTestCase):
                raise TypeError(f"The 'test_metadata' decorator can only be used on methods of instances of 'CCorrectTestCase'")

            __test_reports.append({
                "problem": func.__name__ if problem is None else problem,
                "description": "" if description is None else description,
                "weight": weight,
                "success": False
            })

            self.tester.start(timeout=timeout)
            try:
                func(self, *args, **kwargs)
            except Exception as e:
                push_info_msg(str(e))
                raise e
            else:
                __test_reports[-1]["success"] = True
            finally:
                _push_output()
                pid = gdb.selected_inferior().pid
                self.tester.finish()
                _push_asan_logs(pid)

        return wrapper

    if callable(problem):
        # case where decorator is used without parenthesis, all args should have their default values
        func = problem
        problem = None
        return decorator(func)
    else:
        # case where decorator is used with parenthesis
        return decorator


def push_info_msg(msg):
    if "messages" in __test_reports[-1]:
        __test_reports[-1]["messages"].append(msg)
    else:
        __test_reports[-1]["messages"] = [msg]


def push_tag(tag):
    if "tags" in __test_reports[-1]:
        __test_reports[-1]["tags"].append(tag)
    else:
        __test_reports[-1]["tags"] = [tag]


# TODO this doesnt collect memleaks of libasan because they are printed at the end of the execution
#       --> find a way to do so.
# MAYBE I have no choice than executing the program fully for each test method.
#       --> then I need to create a quick_restart method in the Debugger class that does not resetup everything (sinon c'est lent)
def _push_output():
    gdb.parse_and_eval("(int) fflush(0)")

    # TODO don't truncate (this way we keep the file contents if needed) but keep track of how much has been read
    # read stdout and stderr, then remove their contents for the next test
    with open("stdout.txt", "r") as f:
        __test_reports[-1]["stdout"] = f.read()
    with open("stderr.txt", "r") as f:
        __test_reports[-1]["stderr"] = f.read()

    os.remove("stdout.txt")
    os.remove("stderr.txt")


def _push_asan_logs(pid):
    asan_log_path = f"asan_log.{pid}"
    try:
        with open(asan_log_path, "r") as f:
            __test_reports[-1]["asan_log"] = f.read()
        os.remove(asan_log_path)
    except FileNotFoundError:
        pass


def run_tests(verbosity=0):
    # TODO test_case_classes argument that is used to build test suites
    #      --> only allow 'CCorrectTestCase' subclasses

    try:
        os.remove("results.yml")
    except FileNotFoundError:
        pass

    unittest.main(exit=False, verbosity=verbosity)

    total = len(__test_reports)
    succeeded = 0
    score = 0
    sum_weights = 0
    for r in __test_reports:
        if r["success"]:
            succeeded += 1
            score += r["weight"]
        sum_weights += r["weight"]

    if sum_weights > 0:
        score /= sum_weights

    with open("results.yml", "w") as f:
        data = {
            "summary": {
                "total": total,
                "succeeded": succeeded,
                "failed": total - succeeded,
                "score": round(score * 100, 2),
            },
            "details": __test_reports
        }
        yaml_dump(data=data, stream=f, sort_keys=False)
