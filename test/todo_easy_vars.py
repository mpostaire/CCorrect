from ccorrect.debugger import Debugger
import ccorrect.values as cval


tester = Debugger(source_files=["list.c"])
gdb = tester.start()

# Test basic types
val = cval.value("char", "c")
print(val)

val = cval.value("unsigned int", 42)
print(val)

val = cval.value("int", -42)
print(val)

val = cval.value("float", 42.42)
print(val)

val = cval.value("double", 42.42)
print(val)

# Test basic allocated types
val = cval.value_allocated("char", "c")
print(val.dereference())

val = cval.value_allocated("unsigned int", 42)
print(val.dereference())

val = cval.value_allocated("int", -42)
print(val.dereference())

val = cval.value_allocated("float", 42.42)
print(val.dereference())

val = cval.value_allocated("double", 42.42)
print(val.dereference())

# Test arrays
val = cval.value("int", [1, 2, 3, 4, 42])
print(val)

# Test strings
val = cval.value("char", ["h", "e", "l", "l", "o" ])
print(val)

val = cval.string("hello")
print(val)

val = cval.string_allocated("hello")
print([str(val[i]) for i in range(5)])

# Test pointer allocated of array
val = cval.value_allocated("int", [0, 1, 2, 42])
print([int(val[i]) for i in range(4)])

# Test array of arrays
val = cval.value("int", [[1, 2], [3, 4], [5, 6], [7, 8]])
print(f"{val.type}: {val}")

val = cval.value("int", [[[1, 2, 3], [4, 5, 6]], [[7, 8, 9], [10, 11, 12]], [[1, 2, 3], [4, 5, 6]], [[7, 8, 9], [10, 11, 12]]])
print(f"{val.type}: {val}")

# Test struct
node_struct = {"value": 4, "next": None}
val = cval.value("node", node_struct)
print(val)

# Test nested struct
node_nested_struct = {"value": 4, "next": {"value": 5, "next": None}}
val = cval.value("node_ext", node_nested_struct)
print(val)

# Test struct pointer
val = cval.value_allocated("node_ext", node_nested_struct)
print(val.dereference())

# Test struct nested array
node_struct_nested_array = {"value": 4, "next": [1, 2, 3, 4]}
val = cval.value("node_array", node_struct_nested_array)
print(val)

# Test struct nested array of arrays
node_struct_nested_array = {"value": 4, "next": [[1, 2], [3, 4], [5, 6], [7, 8]]}
val = cval.value("node_array2d", node_struct_nested_array)
print(val)

node_struct_nested_array['next'] = [[[1, 2, 3], [4, 5, 6]], [[7, 8, 9], [10, 11, 12]], [[1, 2, 3], [4, 5, 6]], [[7, 8, 9], [10, 11, 12]]]
val = cval.value("node_array3d", node_struct_nested_array)
print(val)

# /!\ Not supported ----> doable with gdb.parse_and_eval() using malloc for the whole size of the struct and
#                       setting manually the elements
# node_nested_struct_array_variable = {"value": 4, "next": [1, 2, 3, 4]}
# val = cval.value("node_variable_array", node_nested_struct_array_variable)
# print(val)

# Test pointer to nested struct
node_nested_struct_pointer = {"value": 4, "next": {"value": 5, "next": None}}
val = cval.value("node", node_nested_struct_pointer)
print(val)
print(val['next'].dereference())

# Test circular struct
# manually create circular struct using pointers of previously allocated values
tail = cval.value_allocated("node", {"value": 6, "next": None})
middle = cval.value_allocated("node", {"value": 5, "next": cval.Ptr(tail)})
head = cval.value_allocated("node", {"value": 4, "next": cval.Ptr(middle)})

gdb.parse_and_eval(f"((node *) {tail})->next = {head}")

tmp = head.dereference()
print(f"head ({head}): {tmp}")
tmp = tmp['next'].dereference()
print(f"middle ({middle}): {tmp}")
tmp = tmp['next'].dereference()
print(f"tail ({tail}): {tmp}")

# TODO Test struct containing struct of another type

# TODO Test array of structs

# TODO Test array of pointers

# TODO complex structs: multiple types and arrays/structs and arrays of structs
