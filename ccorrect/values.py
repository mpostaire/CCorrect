import gdb
import struct
import sys
from ccorrect import Ptr


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

        for l in reversed(lengths):
            self.type = self.type.array(l)


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
            self.children = [self.value_builder._parse_value(self.type.target(), self.value, self)]

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
            self.value_builder.allocated_addresses.append(address)

        return bytearray(address.to_bytes(self.type.sizeof, sys.byteorder, signed=self.type.is_signed))


class ValueBuilder:
    def __init__(self):
        self.allocated_addresses = []

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

        print(f"{'  ' * level}type={node.type}, value={node.value}")
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
        pointer = gdb.parse_and_eval(f"malloc({root_type.sizeof})")
        inferior = gdb.selected_inferior()
        inferior.write_memory(pointer, obj)

        self.allocated_addresses.append(int(pointer))

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
        for address in self.allocated_addresses:
            gdb.parse_and_eval(f"free({address})")
        self.allocated_addresses = []
