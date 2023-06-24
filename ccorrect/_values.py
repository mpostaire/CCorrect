import gdb
import struct
import sys
import math
from functools import wraps


def gdb_array_iter(value):
    # type_of_elements = value.type.target()
    range_of_array = value.type.fields()[0].type.range()
    len_of_array = range_of_array[1] + 1
    for i in range(len_of_array):
        yield value[i]


def gdb_struct_iter(value):
    for f in value.type.fields():
        yield f.name, value[f.name]


def ensure_self_debugging(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        current_id = gdb.convenience_variable("__CCorrect_debugging")
        if isinstance(self, FuncWrapper):
            self_id = self._valuebuilder._id
        else:
            self_id = self._id

        if current_id is None:
            raise RuntimeError("No program is being run by gdb")
        if current_id != self_id:
            raise RuntimeError(f"Another program is already being run by gdb (running: #{current_id}, self: #{self_id})")

        return func(self, *args, **kwargs)

    return wrapper


def ensure_none_debugging(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        current_id = gdb.convenience_variable("__CCorrect_debugging")
        if current_id is not None:
            raise RuntimeError(f"A program is already being run by gdb (running: #{current_id}, self: #{self._id})")

        return func(self, *args, **kwargs)

    return wrapper


def disable_watch_fail(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        gdb.set_convenience_variable("__CCorrect_disable_watch_fail", True)
        ret = func(self, *args, **kwargs)
        gdb.set_convenience_variable("__CCorrect_disable_watch_fail", False)
        return ret

    return wrapper


def type_is_signed(type):
    try:
        return type.is_signed
    except AttributeError:
        # gdb < 12.1: gdb.Type has no 'is_signed' attribute
        type = type.strip_typedefs().unqualified()
        if type.name is not None:
            return not type.name.startswith("unsigned")
        return False


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
        type = self.type.unqualified().strip_typedefs()
        assert type.code == gdb.TYPE_CODE_INT or type.code == gdb.TYPE_CODE_FLT

        # as floats/doubles in python don't have a to_bytes() method, use struct.pack()
        if isinstance(self.value, float):
            return bytearray(struct.pack("f" if type.name == "float" else "d", self.value))

        if isinstance(self.value, str):
            self.value = ord(self.value[0])

        # Using this method instead of struct.pack() is easier (especially if it's a typedef): no need to build a format string matching the type
        return bytearray(self.value.to_bytes(self.type.sizeof, sys.byteorder, signed=type_is_signed(type)))


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
            padding = (math.ceil(len(bytes) / alignment) * alignment) - len(bytes)  # difference of 'len(bytes)' and its nearest, greater multiple of 'alignment'
            bytes += bytearray(int(0).to_bytes(padding, sys.byteorder))


class UnionNode(ValueNode):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        fields = {f.name: f for f in self.type.fields()}
        for name, value in self.value.items():
            self.children.append(self.value_builder._parse_value(fields[name].type, value, self))

    def to_bytes(self):
        for elem in self.children:
            obj = elem.to_bytes()

        len_diff = self.type.sizeof - len(obj)
        if len_diff > 0:
            obj += bytearray(int(0).to_bytes(len_diff, sys.byteorder))

        return obj


class PointerNode(ValueNode):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.value is not None and not isinstance(self.value, Ptr):
            if isinstance(self.value, str):
                self.value = tuple(self.value + chr(0))

            if isinstance(self.value, (list, tuple)):
                for elem in self.value:
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
            self.value_builder._allocated_addresses.add(address)

        return bytearray(address.to_bytes(self.type.sizeof, sys.byteorder, signed=type_is_signed(self.type)))


class FuncWrapper:
    """
    Extending gdb.Value doesn't always work depending on the gdb version so we make
    a wrapper around a gdb.Value representing a function that parses template arguments.
    """

    def __init__(self, valuebuilder, *args, **kwargs):
        self._valuebuilder = valuebuilder
        self._value = gdb.Value(*args, **kwargs)

    @ensure_self_debugging
    def __call__(self, *args):
        parsed_args = []
        if args is not None:
            arg_types = [field.type for field in self._value.type.fields()]
            for arg, type in zip(args, arg_types):
                if isinstance(arg, FuncWrapper):
                    arg = arg._value
                elif not isinstance(arg, gdb.Value):
                    arg = self._valuebuilder.value(type, arg)
                parsed_args.append(arg)

        return self._value(*parsed_args)

    def __str__(self):
        return str(self._value)


class ValueBuilder:
    _id_counter = 0

    def __init__(self):
        self._allocated_addresses = set()
        self._id = ValueBuilder._id_counter
        ValueBuilder._id_counter += 1

    def _parse_value(self, type, value, parent=None):
        type_code = type.strip_typedefs().code
        if type_code == gdb.TYPE_CODE_PTR:
            # TODO parse given gdb.Type, not value type
            return PointerNode(type, Ptr(0) if value is None else value, self, parent=parent)
        elif isinstance(value, (list, tuple)):
            return ArrayNode(type, value, self, parent=parent)
        elif isinstance(value, dict):
            if type_code == gdb.TYPE_CODE_UNION:
                return UnionNode(type, value, self, parent=parent)
            return StructNode(type, value, self, parent=parent)
        elif type_code == gdb.TYPE_CODE_ENUM:
            return ScalarNode(type.target(), value, self, parent=parent)
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

    @ensure_self_debugging
    @disable_watch_fail
    def _value_allocated(self, type, value):
        obj, root_type = self._value_as_bytes(type, value)

        # print(f"alloc size = {len(obj)}")
        pointer = gdb.parse_and_eval(f"(void *) malloc({len(obj)})")
        inferior = gdb.selected_inferior()
        inferior.write_memory(pointer, obj)

        self._allocated_addresses.add(int(pointer))
        return pointer.cast(root_type.pointer())

    def value(self, type, value):
        """
        Returns a gdb.Value constructed from a python variable (contents are allocated in the inferior's memory)
        """
        return self._value_allocated(type, value).dereference()

    def string(self, str):
        """
        Helper to create a string as a gdb.Value (contents allocated in the inferior's memory)
        """
        return self.value("char", [*str, '\0'])

    def pointer(self, value_or_type, value=None):
        if value is None:
            value = value_or_type
            assert isinstance(value, gdb.Value)
            if value.address is not None:
                return value.address

            assert value.type.code == gdb.TYPE_CODE_PTR
            return self._value_allocated(value.type, Ptr(value))

        type = gdb.lookup_type(value_or_type).pointer()
        return self._value_allocated(type, Ptr(value)).dereference()

    @ensure_self_debugging
    def function(self, funcname):
        return FuncWrapper(self, gdb.parse_and_eval(funcname))

    @ensure_self_debugging
    def functions(self, funcnames):
        return tuple(FuncWrapper(self, gdb.parse_and_eval(funcname)) for funcname in funcnames)

    @ensure_self_debugging
    @disable_watch_fail
    def free_allocated_values(self):
        for address in self._allocated_addresses:
            gdb.parse_and_eval(f"free({address})")
        self._allocated_addresses.clear()
