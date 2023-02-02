import gdb

from ccorrect.debugger import Debugger
tester = Debugger(source_files=["list.c"])
gdb = tester.start()

struct_ptr = gdb.parse_and_eval("$a = (node_variable_array *) malloc(sizeof(node_variable_array) + 2 * sizeof(int))")
gdb.parse_and_eval("$a->value = 42")
gdb.parse_and_eval("$a->next[0] = 32")
gdb.parse_and_eval("$a->next[1] = 16")
# gdb.execute("print *$a")
# gdb.execute("print $a->next[0]")
# gdb.execute("print $a->next[1]")

struct = struct_ptr.dereference()
print(struct.type.fields()[1].type.range())
