<!-- TODO all mentions of functions/methods of CCorrect in this document needs to be converted into links pointing to their repective documentation -->

# How to port a CTester INGInious task to CCorrect

This guide aims to explain how to use CCorrect by showing how to convert an INGInious task using CTester into one using CCorrect to grade and provide feedback for a C exercise. The original task chosen as support can be accessed [here](https://github.com/obonaventure/LEPL1503/tree/master/s3_calloc2/student).


## Task structure

The directory structure of a CCorrect task is the same as a CTester task except for 3 files: the contents of the `run` file can be replaced by the contents of [this file](run)) and the same can be done for the `Makefile` which is replaced by [this one](Makefile).
The most important changes are made to the [tests.c](https://github.com/obonaventure/LEPL1503/tree/master/s3_calloc2/student/tests.c) file: it is removed and replaced by a new file named [test.c](test.c):

```c
/* test.c */
// the following includes are needed by CCorrect
#include <stdlib.h>
#include <unistd.h>

// make mallopt and M_PERTURB symbols available for GDB
#include <malloc.h>

// include functions to test
#include "student_code.h"
#include "solutions/student_code_sol.h"

int main() {
    return 0;
}
```

This file contains an empty `main` function and all the relevant includes. The `main` function doesn't need to do anything as CCorrect itself will execute the functions written by the student. This file only exists to allow CCorrect to create a process to debug with GDB.

The task's `environment_id` must be set to `ccorrect`.

## Porting the tests

Now, we create the file ([test.py](test.py)) that implements the tests. This is where CCorrect is very different than CTester because the tests are written as a Python script and not a C program.

A basic CCorrect test script looks like this:

```python
# test.py
import ccorrect


class TestStudentCode(ccorrect.TestCase):
    debugger = ccorrect.Debugger("test")

    @ccorrect.test_metadata(
        problem="calloc2",
        description="Allocated memory : test calloc2"
    )
    def test_calloc2_1(self):
        ...


ccorrect.run_tests()
```

If we take a look at the `TestStudentCode` class, we see that it extends `ccorrect.TestCase`. A `ccorrect.TestCase` is a subclass of a `TestCase` from the [unittest](https://docs.python.org/3/library/unittest.html) module. It is recommended to read its documentation to understand what are the available methods but note that CCorrect adds some more.

The `run_tests()` function of the `ccorrect` module runs all the tests of all the `TestCase` subclasses in the file. Each `TestCase` subclass must have a `debugger` class variable initialized to a `Debugger` instance. In this example, we pass the path to the compiled `test` program as its argument. Only methods of a `ccorrect.TestCase` starting with the `test` prefix are run by `ccorrect.run_tests()`, and they are run in lexicographic order of their name.

If we look at the original [tests.c](https://github.com/obonaventure/LEPL1503/tree/master/s3_calloc2/student/tests.c) file, it contains 3 test functions. The example above only considers the first one, `test_calloc2_1`, for now. Here is what the first line of this function looks like originally:

```c
// tests.c
void test_calloc2_1() {
	set_test_metadata("calloc2", _("Allocated memory : test calloc2"), 1);
    ...
}
```

The first line of this function sets the problem name, a description and a weight. In CCorrect, this is done by using the `test_metadata` decorator on top of a test method. In our example, only the problem name and the description are set because the weight is 1 by default. It can also be set to a custom value.

Lets now look at the next few lines of the implementation.

```c
// tests.c
void test_calloc2_1() {
    ...
    monitored.malloc = true;
    failures.malloc = FAIL_NEVER;

    ...

    SANDBOX_BEGIN;
    ret = calloc2(16, 4);
    if (ret == NULL) {
        flag = 0;
        CU_FAIL("Erreur lors l'allocation de la mémoire.");
        return;
    }
    SANDBOX_END;
    ...
}
```

The code, once ported to CCorrect, looks like this:

```python
# test.py
...
@ccorrect.test_metadata(
    problem="calloc2",
    description="Allocated memory : test calloc2"
)
def test_calloc2_1(self):
    ...
    calloc2 = self.debugger.function("calloc2")

    with self.debugger.watch("malloc"):
        ret = calloc2(16, 4)
        if ret == 0:
            flag = False
            self.fail("Erreur lors l'allocation de la mémoire.")
    ...
```

We use `self.debugger.function("calloc2")` to get a `FuncWrapper` that can be called from inside CCorrect. `calloc2` is the function the student has implemented for this task. Once called, GDB executes the `calloc2` function inside the debugged process and the test script stops until the function returns.

To monitor a function's call arguments, return values and how many times it has been called, we use the `watch` method of `Debugger` in a with statement and on the `malloc` function. While the test script's execution is inside the scope of this with statement, every call to `malloc` by the debugger process is recorded.

Looking further into the original `test_calloc2_1`, we see that the size of allocated memory by `calloc2` is tracked using the `start` and `used_size` variables:

```c
/* tests.c */
void test_calloc2_1() {
    ...
    size_t  start = stats.memory.used;

    SANDBOX_BEGIN;
    ...
    SANDBOX_END;

    size_t used_size = stats.memory.used - start;

    CU_ASSERT_EQUAL(used_size, 16 * 4);
    if (used_size != 16 * 4) {
        flag = 0;
        set_tag("wrong_alloc_size");	
        push_info_msg(_("You allocated more memory than required."));
    }
    ...
}
```

CCorrect can achieve the same using the `allocated_size` of `Debugger`:

```python
# test.py
...
@ccorrect.test_metadata(
    problem="calloc2",
    description="Allocated memory : test calloc2"
)
def test_calloc2_1(self):
    ...
    if self.debugger.allocated_size() != 16 * 4:
        flag = False
        self.push_tag("not_malloc_once")
        self.fail("You allocated more memory than required.")
    ...
```

Note that CCorrect sets INGInious tags with the `push_tag` method of `TestCase`.

Finally, the rest of the `test_calloc2_1` function is as follows:

```c
/* tests.c */
void test_calloc2_1() {
    ...
    CU_ASSERT_PTR_NOT_NULL(ret);

    CU_ASSERT_TRUE(malloced(ret));
    if (!malloced(ret) || ret == NULL) {
        flag = 0;
    }

    CU_ASSERT_EQUAL(stats.malloc.called, 1)
    if (stats.malloc.called != 1) {
        flag = 0;
        set_tag("not_malloc_once");
        push_info_msg(_("Why didn't you call malloc exactly once?"));
    }

    free(ret);
}
```

It is converted to CCorrect code like this (note that `flag` is a global variable, so it must be set as such, as is done at the beginning of the `test_calloc2_1` method):

```python
# test.py
...
@ccorrect.test_metadata(
    problem="calloc2",
    description="Allocated memory : test calloc2"
)
def test_calloc2_1(self):
    global flag

    ...

    if ret == 0 or not self.debugger.malloced(ret):
        flag = False

    if self.debugger.stats["malloc"].called != 1:
        flag = False
        self.push_tag("not_malloc_once")
        self.fail("Why didn't you call malloc exactly once?")
```

Note that we do not need to free `ret` as the debugged process is exited just after a test method execution.

Now that `test_calloc2_1` has been ported to CCorrect, `test_calloc2_2` and `test_calloc2_3` can be done as well following the same principles. The final file can be seen [there](test.py). Note that `test_calloc2_2` uses `mallopt` to set the `M_PERTURB` memory allocation parameter. This is not needed as CCorrect enables this parameter by itself.
