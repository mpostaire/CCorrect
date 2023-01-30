import struct
import sys

from ccorrect.debugger import Debugger
tester = Debugger(source_files=["list.c"])
gdb = tester.start()


def scalar_to_bytes(type, value):
    # as floats/doubles in python don't have a to_bytes() method, use struct.pack()
    if isinstance(value, float):  # TODO detection for double (d) or float (f)
        return bytearray(struct.pack("f" if type.strip_typedefs().name == "float" else "d", value))

    if type.name == "char" or type.name == "unsigned char" or type.name == "signed char":
        return bytearray(value.encode())

    # Using this method instead of struct.pack() is easier (especially if it's a typedef): no need to build a format string matching the type
    return bytearray(value.to_bytes(type.sizeof, sys.byteorder, signed=type.is_signed if type.is_scalar else False))


# TODO doesn't work for structures with __attribute__((packed))
#       ---> check if works with aligned_alloc
# FIX idea: if sizeof % alignof != 0, we have a packed struct but gdb reports a wrong alignment: replace gdb's align by sizeof(smallest_type_in_struct)
def align_bytes(bytes, alignment):
    if len(bytes) % alignment != 0:  # TODO fix align handling (should check that is is a multiple of align, if not, append padding zeroes to make it multiple)
        padding = abs(alignment - len(bytes))
        bytes += bytearray(int(0).to_bytes(padding, sys.byteorder))


# TODO extend this to all possible C types (as of now it only as incomplete supports for structs)
# how to handle unions, enums?
def pyval_to_gdbval(type, value):
    # TODO using gdb.lookup_type(type), get info on the type (and underlying types using recursion (don't recurse inside pointer tho)) to convert
    #                           ----------> If recurse inside pointers, make a cycle detection to avoid stack overflow ----> use id(value) to get its address (or 'is' operator????)
    # any native python value into a gdb.Value
    truetype = gdb.lookup_type(type)

    print(f"sizeof={truetype.sizeof}, alignof={truetype.alignof}")

    if truetype.is_scalar:
        obj = scalar_to_bytes(truetype, value)
        return gdb.Value(obj, truetype)

    # TODO this code is not finished
    # for example it does not support pointers detection like this: {"value": 4, "next": {"value": 5, "next": 0}}
    # in this case the next points to another dict. This dict should be parsed, then allocated in the inferior and its pointer put into its parent
    fields = truetype.fields()
    obj = bytearray()
    for f in fields:
        # print(f"{f.name} -> {f.type}")
        obj += scalar_to_bytes(f.type, value[f.name])
        align_bytes(obj, truetype.alignof)
        print(obj)

    # print(obj)
    return gdb.Value(obj, truetype)

node_struct = {"value": 4, "next": 0}
val = pyval_to_gdbval("node", node_struct)
gdb.set_convenience_variable("val", val)
gdb.execute("print $val")

val = pyval_to_gdbval("char", "c")
gdb.set_convenience_variable("val", val)
gdb.execute("print $val")

val = pyval_to_gdbval("unsigned int", 42)
gdb.set_convenience_variable("val", val)
gdb.execute("print $val")

val = pyval_to_gdbval("int", -42)
gdb.set_convenience_variable("val", val)
gdb.execute("print $val")

val = pyval_to_gdbval("float", 42.42)
gdb.set_convenience_variable("val", val)
gdb.execute("print $val")

val = pyval_to_gdbval("double", 42.42)
gdb.set_convenience_variable("val", val)
gdb.execute("print $val")
