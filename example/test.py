import sys

sys.path.append("../")

import ccorrect

# TODO is there is an assertion error, memleak can trigger but we don't want this...
# TODO what if ccorrect.run() is called multiple times? maybe should prevent that
with ccorrect.test("main", source_files=["list.c"], silent_gdb=False) as tester:
    list_ptr = tester.pointer(tester.pointer("node", 0))

    nullptr = tester.pointer("void", 0)
    tester.fail("malloc", nullptr)

    push_ret = tester.call("push", [list_ptr, 42])

    tester.stop_fail("malloc")

    assert tester.stats["malloc"].called == 1
    assert tester.stats["malloc"].returns[0] == 0 and push_ret == -1

    push_ret = tester.call("push", [list_ptr, 42])

    assert tester.stats["malloc"].called == 2
    # ensures that push() returns 0 if malloc succeeds
    assert tester.stats["malloc"].returns[1] and push_ret == 0

    push_ret = tester.call("push", [list_ptr, 24])

    assert tester.stats["malloc"].called == 3
    # ensures that push() returns 0 if malloc succeeds
    assert tester.stats["malloc"].returns[2] and push_ret == 0

    # list_ptr['value'] is equivalent to list_ptr.dereference().dereference()['value']
    assert list_ptr['value'] == 24
    assert list_ptr['next']['value'] == 42

    pop_ret = tester.call("pop", [list_ptr])

    assert tester.stats["free"].called == 1
    assert pop_ret == 24

    pop_ret = tester.call("pop", [list_ptr])

    assert tester.stats["free"].called == 2
    assert pop_ret == 42

    # try:
    #     tester.call("memleak")
    #     # tester.call("out_of_bounds")
    # except:
    #     exit(1)

    # free allocated values to avoid a false positive memory leak report by the leak sanitizer
    tester.free_allocated_values()
