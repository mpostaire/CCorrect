import gdb
import struct
import sys

def gdb_array_iterator(value):
    assert value.type.code == gdb.TYPE_CODE_ARRAY
    # type_of_elements = value.type.target()
    range_of_array = value.type.fields()[0].type.range()
    len_of_array = range_of_array[1] + 1
    for i in range(len_of_array):
        yield value[i]


def gdb_struct_iterator(value):
    for f in value.type.fields():
        yield f.name, value[f.name]


class ValueNode:
    def __init__(self, type, value, parent=None):
        self.type = type
        self.value = value
        self.parent = parent
        self.children = []


class ScalarNode(ValueNode):
    def to_bytes(self):
        # as floats/doubles in python don't have a to_bytes() method, use struct.pack()
        if isinstance(self.value, float):
            return bytearray(struct.pack("f" if self.type.strip_typedefs().name == "float" else "d", self.value))

        if self.type.name == "char" or self.type.name == "unsigned char" or self.type.name == "signed char":
            return bytearray(self.value.encode())

        # Using this method instead of struct.pack() is easier (especially if it's a typedef): no need to build a format string matching the type
        return bytearray(self.value.to_bytes(self.type.sizeof, sys.byteorder, signed=self.type.is_signed if self.type.is_scalar else False))


class ArrayNode(ValueNode):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.parent:
            # no parent means this as currently the type of its innermost elements and it
            # needs to be set to an actual array type
            self.__set_root_type()

        for elem in self.value:
            self.children.append(parse_value(self.type.target(), elem, self))

    def to_bytes(self):
        obj = bytearray()
        for elem in self.children:
            obj += elem.to_bytes()
        return obj

    def __set_root_type(self):
        value = self.value
        lengths = []

        while isinstance(value, (list, tuple)):
            lengths.append(len(value) - 1)
            value = value[0]

        for l in reversed(lengths):
            self.type = self.type.array(l)


class StructNode(ValueNode):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for f in self.type.fields():
            self.children.append(parse_value(f.type, self.value[f.name], self))

    def to_bytes(self):
        obj = bytearray()
        for elem in self.children:
            obj += elem.to_bytes()
            self.__align_bytes(obj)
        return obj

    # TODO doesn't work for structures with __attribute__((packed))
    #       ---> check if works with aligned_alloc
    # FIX idea: if sizeof % alignof != 0, we have a packed struct but gdb reports a wrong alignment: replace gdb's align by sizeof(smallest_type_in_struct)
    def __align_bytes(self, bytes):
        alignment = self.type.alignof
        if len(bytes) % alignment != 0:  # TODO fix align handling (should check that is is a multiple of align, if not, append padding zeroes to make it multiple)
            padding = abs(alignment - len(bytes))
            bytes += bytearray(int(0).to_bytes(padding, sys.byteorder))


class PointerNode(ValueNode):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.value is not None and not isinstance(self.value, Ptr):
            self.children = [parse_value(self.type.target(), self.value, self)]

    def to_bytes(self):
        if isinstance(self.value, Ptr):
            address = self.value
        else:
            child = self.children[0]
            obj = child.to_bytes()

            # print(f"alloc size = {child.type.sizeof}")
            pointer = gdb.parse_and_eval(f"malloc({child.type.sizeof})")
            inferior = gdb.selected_inferior()
            inferior.write_memory(pointer, obj)

            address = int(pointer)

        return bytearray(address.to_bytes(self.type.sizeof, sys.byteorder, signed=self.type.is_signed))


class Ptr(int):
    def __init__(self, value):
        if value < 0:
            raise ValueError(f"Ptr must be 0 or positive (got {value})")

    def __str__(self):
        return hex(self)


def parse_value(type, value, parent=None):
    if type.code == gdb.TYPE_CODE_PTR:
        return PointerNode(type, Ptr(0) if value is None else value, parent=parent)
    elif isinstance(value, (list, tuple)):
        return ArrayNode(type, value, parent=parent)
    elif isinstance(value, dict):
        return StructNode(type, value, parent=parent)
    else:
        return ScalarNode(type, value, parent=parent)


def _value_as_bytes(type, value):
    if not isinstance(type, gdb.Type):
        type = gdb.lookup_type(type).strip_typedefs()

    root = parse_value(type, value)
    # print_tree(root)
    return root.to_bytes(), root.type


def print_tree(node, level=0):
    if level == 0:
        print("----------------")

    print(f"{'  ' * level}type={node.type.strip_typedefs()}, value={node.value}")
    for child in node.children:
        print_tree(child, level=level + 1)

    if level == 0:
        print("----------------")


def value(type, value):
    """
    Returns a gdb.Value constructed from a python variable
    """
    if not isinstance(type, gdb.Type):
        type = gdb.lookup_type(type).strip_typedefs()

    obj, root_type = _value_as_bytes(type, value)
    return gdb.Value(obj, root_type)


# TODO keep track of allocated values to free them afterwards
def value_allocated(type, value):
    """
    Returns a gdb.Value pointer to value (contents are allocated in the inferior's memory)
    """
    if not isinstance(type, gdb.Type):
        type = gdb.lookup_type(type).strip_typedefs()

    obj, root_type = _value_as_bytes(type, value)

    # print(f"alloc size = {root_type.sizeof}")
    pointer = gdb.parse_and_eval(f"malloc({root_type.sizeof})")
    inferior = gdb.selected_inferior()
    inferior.write_memory(pointer, obj)

    if root_type.code == gdb.TYPE_CODE_ARRAY:
        return pointer.cast(root_type.target().pointer())
    else:
        return pointer.cast(root_type.pointer())


def string(str):
    """
    Helper to create a string as a gdb.value
    """
    return value("char", [*str])


def string_allocated(str):
    """
    Helper to create a string as a gdb.value (contents allocated in the inferior's memory)
    """
    return value_allocated("char", [*str])


def pointer(referenced_value):
    """
    Returns a gdb.Value pointer to referenced_value
    referenced_value must be located in the memory of the inferior
    """
    if referenced_value.address is None:
        raise ValueError("Cannot get reference of referenced_value: not a variable of the inferior")

    type = referenced_value.type.pointer()
    return value(type, int(referenced_value.address))
