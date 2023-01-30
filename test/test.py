from ccorrect.debugger import Debugger

tester = Debugger(source_files=["list.c"])

gdb = tester.start()

# /!\ gdb calls malloc for these 2 lines but it seems they aren't caught in tester.stats /!\
gdb.execute("set $head = (node *) &{42}")
gdb.execute("set $list = (node *) &{$head}")

head_val = gdb.convenience_variable('head').dereference()
print(f"\t*head: {head_val['value']}")

push_ret = gdb.parse_and_eval("push($list, 24)")
print(f"\tpush_ret: {push_ret}")

# malloc has been called exactly once
assert tester.stats["malloc"].called == 1
# ensures that push() returns 0 if malloc succeeds
assert tester.stats["malloc"].returns[0] and push_ret == 0

print(f"\t{tester.stats}")
