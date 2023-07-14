import gdb
import struct
import sys
import math
from functools import wraps


def gdb_array_iter(value):
    """Iterator for a `gdb.Value` representing an array. Returns each elements of the array."""
    range_of_array = value.type.fields()[0].type.range()
    len_of_array = range_of_array[1] + 1
    for i in range(len_of_array):
        yield value[i]


def gdb_struct_iter(value):
    """Iterator for a `gdb.Value` representing a struct. Returns tuples of each struct member name and their value."""
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
    """
    Wrapping an `int` value with this class tells the template parser that the wrapped value is the actual value of the pointer.
    
    This is useful because the template parser would have created a new pointer pointing to the `int` value instead.

    Usage example::

        debugger = Debugger("program")
        debugger.start()

        type = gdb.lookup_type("int").pointer()
        val = self.value(type, 42)  # This creates a pointer pointing to an int with a value of 42.
        val = self.value(type, Ptr(42))  # This creates a pointer pointing to memory address 42.
        val = self.pointer("int", 42)  # This is equivalent to the line above.

        debugger.finish()
    """

    def __init__(self, value):
        if value < 0:
            raise ValueError(f"Ptr must be >= 0 (got {value})")

    def __str__(self):
        return hex(self)


class ValueNode:
    def __init__(self, type, template, value_builder, parent=None):
        self.type = type
        self.template = template
        self.value_builder = value_builder
        self.parent = parent
        self.children = []


class ScalarNode(ValueNode):
    def to_bytes(self):
        type = self.type.unqualified().strip_typedefs()

        # as floats/doubles in python don't have a to_bytes() method, use struct.pack()
        if isinstance(self.template, float):
            assert type.code == gdb.TYPE_CODE_FLT
            return bytearray(struct.pack("f" if type.name == "float" else "d", self.template))

        assert type.code == gdb.TYPE_CODE_INT or type.code == gdb.TYPE_CODE_PTR or type.code == gdb.TYPE_CODE_VOID

        if isinstance(self.template, str):
            self.template = ord(self.template[0])

        # Using this method instead of struct.pack() is easier (especially if it's a typedef): no need to build a format string matching the type
        return bytearray(self.template.to_bytes(self.type.sizeof, sys.byteorder, signed=type_is_signed(type)))


class ArrayNode(ValueNode):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.parent:
            # no parent means this as currently the type of its innermost elements and it
            # needs to be set to an actual array type
            self.__set_root_type()

        for elem in self.template:
            self.children.append(self.value_builder._parse_template(self.type.target(), elem, self))

    def to_bytes(self):
        obj = bytearray()
        for elem in self.children:
            obj += elem.to_bytes()
        return obj

    def __set_root_type(self):
        template = self.template
        lengths = []

        while isinstance(template, (list, tuple)):
            lengths.append(len(template) - 1)
            template = template[0]

        for length in reversed(lengths):
            self.type = self.type.array(length)


class StructNode(ValueNode):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for f in self.type.fields():
            self.children.append(self.value_builder._parse_template(f.type, self.template[f.name], self))

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
        for name, template in self.template.items():
            self.children.append(self.value_builder._parse_template(fields[name].type, template, self))

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
        if self.template is not None and not isinstance(self.template, Ptr):
            if isinstance(self.template, str):
                self.template = tuple(self.template + chr(0))

            if isinstance(self.template, (list, tuple)):
                for elem in self.template:
                    self.children.append(self.value_builder._parse_template(self.type.target(), elem, self))
            else:
                self.children = [self.value_builder._parse_template(self.type.target(), self.template, self)]

    def to_bytes(self):
        if isinstance(self.template, Ptr):
            address = self.template
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
    Extending `gdb.Value` doesn't always work depending on the gdb version so we make
    a wrapper around a `gdb.Value` representing a function that parses template arguments.
    """

    def __init__(self, valuebuilder, function):
        self._valuebuilder = valuebuilder
        self._value = gdb.parse_and_eval(function)
        if self._value.type.strip_typedefs().unqualified().code != gdb.TYPE_CODE_FUNC:
            raise ValueError(f"'{function}' is not a valid function identifier")

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

    def _parse_template(self, type, template, parent=None):
        type_code = type.strip_typedefs().unqualified().code
        if type_code == gdb.TYPE_CODE_PTR:
            return PointerNode(type, Ptr(0) if template is None else template, self, parent=parent)
        elif isinstance(template, (list, tuple)):
            return ArrayNode(type, template, self, parent=parent)
        elif isinstance(template, dict):
            if type_code == gdb.TYPE_CODE_UNION:
                return UnionNode(type, template, self, parent=parent)
            return StructNode(type, template, self, parent=parent)
        elif type_code == gdb.TYPE_CODE_ENUM:
            return ScalarNode(type.target(), template, self, parent=parent)
        else:
            return ScalarNode(type, template, self, parent=parent)

    def _value_as_bytes(self, type, template):
        if not isinstance(type, gdb.Type):
            type = gdb.lookup_type(type)

        root = self._parse_template(type, template)
        # self._print_tree(root)
        return root.to_bytes(), root.type

    def _print_tree(self, node, level=0):
        if level == 0:
            print("----------------")

        nullchar_repr = '\\x00'
        print(f"{'  ' * level}type={node.type}, template={str(node.template).replace(chr(0), nullchar_repr)}")
        for child in node.children:
            self._print_tree(child, level=level + 1)

        if level == 0:
            print("----------------")

    @ensure_self_debugging
    @disable_watch_fail
    def _value_allocated(self, type, template):
        obj, root_type = self._value_as_bytes(type, template)

        # print(f"alloc size = {len(obj)}")
        pointer = gdb.parse_and_eval(f"(void *) malloc({len(obj)})")
        gdb.selected_inferior().write_memory(pointer, obj)

        self._allocated_addresses.add(int(pointer))
        return pointer.cast(root_type.pointer())

    def value(self, type, template):
        """
        Returns a `gdb.Value` constructed from a type and a template (contents are allocated in the inferior's memory).
        A template is either a python int, float, str, list or dictionnary that is parsed to easily construct a `gdb.Value`.
        This method can create scalars (int, char, float, pointers, enums values, ...) and aggregates (arrays, stucts, unions).

        The `type` argument must be a string representing the identifier of a type.

        The `template` argument is either a `int`, `float`, `str`, `list` or a `dict`.

        If the template is a `list`, its elements must be templates and the returned `gdb.Value` will be an array of the elements from the list.

        In the case where the given `type` is a struct or an union, the template must be a `dict` whose keys are strings representing
        each member's identifier and the values are templates.

        Usage example::

            debugger = Debugger("program")
            debugger.start()

            val = debugger.value("int", 42)  # Creates an int with a value of 42.
            val = debugger.value("int", [0, 1, 2, 3])  # Creates an int array of 4 elements with values 0, 1, 2 and 3.
            val = debugger.value("char", ["H", "e", "l", "l", "o", "!", 0])  # Creates a char array containing the string "Hello!".
            val = debugger.value("struct student", {"id": 2468, "grades": [13, 12, 8, 17]})  # Creates a struct student.

            debugger.finish()
        """
        return self._value_allocated(type, template).dereference()

    def string(self, str):
        """
        Helper to create a string as a `gdb.Value`.

        Usage example::

            debugger = Debugger("program")
            debugger.start()

            # The 2 following lines are equivalent:
            val = debugger.value("char", ["H", "e", "l", "l", "o", "!", 0]).cast(gdb.lookup_type("char").pointer())
            val = debugger.string("Hello!")

            debugger.finish()
        """
        return self.value("char", [*str, '\0']).cast(gdb.lookup_type("char").pointer())

    def pointer(self, value_or_type, value=None):
        """
        Returns a `gdb.Value` representing a pointer. It can be used to get a pointer towards a `gdb.Value` or create a pointer pointing to the given value.
        """
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
    @disable_watch_fail
    def allocate(self, size, value=None):
        """
        Returns a `gdb.Value` representing a pointer towards an allocated memory region of `size` bytes in wich each byte is set to `value`.

        `value` can be either `None`, any number in the range [0, 255] or a function that returns such a number and that is called for every position of the allocated memory region.
        If it is a function, it has one argument that is the 0-indexed position in the allocated memory region.
        If it is `None`, this has the same effect as just calling `malloc`.

        Usage example::

            debugger = Debugger("program")
            debugger.start()

            # Allocate 3 bytes all set to 42.
            ptr1 = debugger.allocate(3, 42)

            # Allocate 10 bytes each set to different random values between 0 and 255 (bounds included).
            ptr2 = debugger.allocate(10, lambda i: randint(0, 255))

            # Allocate 6 bytes where the ith byte is set to i.
            ptr3 = debugger.allocate(6, lambda i: i)

            debugger.finish()
        """
        ptr = gdb.parse_and_eval(f"(void *) malloc({size})")

        if value is not None:
            obj = bytearray(value(i) if callable(value) else value for i in range(size))
            gdb.selected_inferior().write_memory(ptr, obj, size)

        self._allocated_addresses.add(int(ptr))
        return ptr

    @ensure_self_debugging
    def function(self, funcname):
        """
        Returns a `FuncWrapper` representing a function from a string represention a function identifier.
        `FuncWrapper` wraps a `gdb.Value`, allowing to call it with templates as arguments.

        Usage example::

            debugger = Debugger("program")
            debugger.start()

            malloc = debugger.function("malloc")
            ptr = malloc(12)

            debugger.finish()
        """
        return FuncWrapper(self, funcname)

    @ensure_self_debugging
    def functions(self, funcnames):
        """
        Returns multiple `FuncWrapper` representing functions at once from a list of strings representing functions identifiers.

        Usage example::

            debugger = Debugger("program")
            debugger.start()

            malloc, free = debugger.functions(["malloc", "free"])
            ptr = malloc(12)
            # Do something...
            free(ptr)

            debugger.finish()
        """
        return tuple(FuncWrapper(self, funcname) for funcname in funcnames)

    @ensure_self_debugging
    @disable_watch_fail
    def free_allocated_values(self):
        """
        Free all allocated values created by the `value`, `pointer` and `string` methods. This is called by default by the `finish` method.
        """
        for address in self._allocated_addresses:
            gdb.parse_and_eval(f"free({address})")
        self._allocated_addresses.clear()
