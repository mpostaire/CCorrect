import gdb
import struct
import sys


def gdb_array_iterator(value):
    # type_of_elements = value.type.target()
    range_of_array = value.type.fields()[0].type.range()
    len_of_array = range_of_array[1] + 1
    for i in range(len_of_array):
        yield value[i]


def gdb_struct_iterator(value):
    for f in value.type.fields():
        yield f.name, value[f.name]


class Ptr(int):
    def __init__(self, value):
        if value < 0:
            raise ValueError(f"Ptr must be >= 0 (got {value})")

    def __str__(self):
        return hex(self)


class ValueNode:
    def __init__(self, type, value, value_builder, parent=None):
        self.type = type
        self.value = value
        self.value_builder = value_builder
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
            self.children.append(self.value_builder._parse_value(self.type.target(), elem, self))

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

        for length in reversed(lengths):
            self.type = self.type.array(length)


class StructNode(ValueNode):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for f in self.type.fields():
            self.children.append(self.value_builder._parse_value(f.type, self.value[f.name], self))

    def to_bytes(self):
        obj = bytearray()
        for elem in self.children:
            obj += elem.to_bytes()
            self.__align_bytes(obj)
        return obj

    def __align_bytes(self, bytes):
        # print(f"sizeof={self.type.sizeof} alignof={self.type.alignof}", file=sys.stderr)

        alignment = self.type.alignof
        # is this struct packed (type.alignof is not 1, we need to manually check for this case)
        if self.type.sizeof % alignment != 0:
            alignment = 1

        if len(bytes) % alignment != 0:
            padding = abs(alignment - len(bytes))
            bytes += bytearray(int(0).to_bytes(padding, sys.byteorder))


class PointerNode(ValueNode):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.value is not None and not isinstance(self.value, Ptr):
            if isinstance(self.value, str):
                for elem in self.value + chr(0):
                    self.children.append(self.value_builder._parse_value(self.type.target(), elem, self))
            else:
                self.children = [self.value_builder._parse_value(self.type.target(), self.value, self)]

    def to_bytes(self):
        if isinstance(self.value, Ptr):
            address = self.value
        else:
            obj = bytearray()
            for child in self.children:
                obj += child.to_bytes()

            pointer = gdb.parse_and_eval(f"(void *) malloc({len(obj)})")
            inferior = gdb.selected_inferior()
            inferior.write_memory(pointer, obj)

            address = int(pointer)
            self.value_builder.allocated_addresses.add(address)

        return bytearray(address.to_bytes(self.type.sizeof, sys.byteorder, signed=self.type.is_signed))


class ValueBuilder:
    def __init__(self):
        self.allocated_addresses = set()

    def _parse_value(self, type, value, parent=None):
        if type.code == gdb.TYPE_CODE_PTR:
            return PointerNode(type, Ptr(0) if value is None else value, self, parent=parent)
        elif isinstance(value, (list, tuple)):
            return ArrayNode(type, value, self, parent=parent)
        elif isinstance(value, dict):
            return StructNode(type, value, self, parent=parent)
        else:
            return ScalarNode(type, value, self, parent=parent)

    def _value_as_bytes(self, type, value):
        if not isinstance(type, gdb.Type):
            type = gdb.lookup_type(type)

        root = self._parse_value(type, value)
        # self._print_tree(root)
        return root.to_bytes(), root.type

    def _print_tree(self, node, level=0):
        if level == 0:
            print("----------------")

        nullchar_repr = '\\x00'
        print(f"{'  ' * level}type={node.type}, value={str(node.value).replace(chr(0), nullchar_repr)}")
        for child in node.children:
            self._print_tree(child, level=level + 1)

        if level == 0:
            print("----------------")

    def value(self, type, value):
        """
        Returns a gdb.Value constructed from a python variable
        """
        if not isinstance(type, gdb.Type):
            type = gdb.lookup_type(type)

        obj, root_type = self._value_as_bytes(type, value)
        return gdb.Value(obj, root_type)

    def value_allocated(self, type, value):
        """
        Returns a gdb.Value pointer to value (contents are allocated in the inferior's memory)
        """
        if not isinstance(type, gdb.Type):
            type = gdb.lookup_type(type)

        obj, root_type = self._value_as_bytes(type, value)

        # print(f"alloc size = {root_type.sizeof}")
        pointer = gdb.parse_and_eval(f"(void *) malloc({root_type.sizeof})")
        inferior = gdb.selected_inferior()
        inferior.write_memory(pointer, obj)

        self.allocated_addresses.add(int(pointer))

        if root_type.code == gdb.TYPE_CODE_ARRAY:
            return pointer.cast(root_type.target().pointer())
        else:
            return pointer.cast(root_type.pointer())

    def string(self, str):
        """
        Helper to create a string as a gdb.value
        """
        return self.value("char", [*str, '\0'])

    def string_allocated(self, str):
        """
        Helper to create a string as a gdb.value (contents allocated in the inferior's memory)
        """
        return self.value_allocated("char", [*str, '\0'])

    def pointer(self, value_or_type, value=None):
        if value is None:
            value = value_or_type
            assert isinstance(value, gdb.Value)
            assert value.type.code == gdb.TYPE_CODE_PTR
            return self.value_allocated(value.type, Ptr(value))

        assert isinstance(value_or_type, str)
        type = gdb.lookup_type(value_or_type).pointer()
        return self.value(type, Ptr(value))

    def free_allocated_values(self):
        # copy self.allocated_addresses to not confuse the iterator as self.allocated_addresses is updated as addresses are freed
        allocated_addresses = self.allocated_addresses.copy()
        for address in allocated_addresses:
            gdb.parse_and_eval(f"free({address})")
        allocated_addresses.clear()
