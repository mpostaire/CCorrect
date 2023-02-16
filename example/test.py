from ccorrect.debugger import Debugger
import ccorrect.values as cval

tester = Debugger(source_files=["list.c"])

gdb = tester.start()

list_ptr = cval.pointer(cval.pointer("node"))

push_ret = tester.call("push", [list_ptr, 42])

assert tester.stats["malloc"].called == 1
# ensures that push() returns 0 if malloc succeeds
assert tester.stats["malloc"].returns[0] and push_ret == 0

push_ret = tester.call("push", [list_ptr, 24])

assert tester.stats["malloc"].called == 2
# ensures that push() returns 0 if malloc succeeds
assert tester.stats["malloc"].returns[1] and push_ret == 0

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
cval.free_allocated_values()

tester.finish()
