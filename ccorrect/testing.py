import os
import unittest
from functools import wraps
from yaml import safe_dump as yaml_dump

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


def test_metadata(problem=None, description=None, weight=1, timeout=5):
    assert weight >= 0
    assert timeout >= 5

    def decorator(func):
        func.__CCorrect_metadata_wrapped = True

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not isinstance(self, CCorrectTestCase):
                raise TypeError(f"The 'test_metadata' decorator can only be used on methods of instances of 'CCorrectTestCase'")

            __test_reports.append({
                "problem": func.__name__ if problem is None else problem,
                "description": "" if description is None else description,
                "weight": weight
            })

            try:
                func(self, *args, **kwargs)
            except Exception as e:
                __test_reports[-1]["success"] = False
                push_info_msg(str(e))
                raise e
            __test_reports[-1]["success"] = True

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


def run_tests():
    try:
        os.remove("results.yml")
    except FileNotFoundError:
        pass

    unittest.main(exit=False)

    total = len(__test_reports)

    succeeded = 0
    weighted_score = 0
    sum_weights = 0
    for r in __test_reports:
        if r["success"]:
            succeeded += 1
            weighted_score += r["weight"]
        sum_weights += r["weight"]

    if sum_weights > 0:
        weighted_score /= sum_weights

    with open("results.yml", "w") as f:
        data = {
            "summary": {
                "total": total,
                "succeeded": succeeded,
                "failed": total - succeeded,
                "weighted_score": round(weighted_score * 100, 2),
            },
            "details": __test_reports
        }
        yaml_dump(data=data, stream=f, sort_keys=False)
