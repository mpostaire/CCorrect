from ccorrect.debugger import Debugger
import ccorrect.values as cval

tester = Debugger(source_files=["list.c"])

gdb = tester.start()

head = cval.value_allocated("node", {"value": 42, "next": None})
head_ptr = cval.pointer(head)

push_ret = tester.call("push", [head_ptr, 24])

assert tester.stats["malloc"].called == 1
# ensures that push() returns 0 if malloc succeeds
assert tester.stats["malloc"].returns[0] and push_ret == 0

assert head_ptr.dereference().dereference()['value'] == 24
assert head_ptr.dereference().dereference()['next']['value'] == 42

pop_ret = tester.call("pop", [head_ptr])

assert tester.stats["free"].called == 1
assert pop_ret == 24

# try:
#     tester.call("memleak")
#     # tester.call("out_of_bounds")
# except:
#     exit(1)

# free allocated values to avoid a memory leak report by the leak sanitizer
cval.free_allocated_values()

tester.finish()
