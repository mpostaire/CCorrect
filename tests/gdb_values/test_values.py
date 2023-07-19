import ccorrect
import unittest
import os
import gdb


program = os.path.join(os.path.dirname(__file__), "main")
debugger = ccorrect.Debugger(program)


class TestValues(unittest.TestCase):
    def setUp(self):
        debugger.start()

    def tearDown(self):
        debugger.free_allocated_values()
        debugger.stats.clear()
        debugger.finish()

    def test_basic_types(self):
        val = debugger.value("char", "c")
        self.assertEqual(chr(val), "c")
        self.assertEqual(str(gdb.lookup_type("char")), str(val.type))

        val = debugger.value("unsigned int", 42)
        self.assertEqual(int(val), 42)
        self.assertEqual(str(gdb.lookup_type("unsigned int")), str(val.type))

        val = debugger.value("short", -42)
        self.assertEqual(int(val), -42)
        self.assertEqual(str(gdb.lookup_type("short")), str(val.type))

        val = debugger.value("int", -42)
        self.assertEqual(int(val), -42)
        self.assertEqual(str(gdb.lookup_type("int")), str(val.type))

        val = debugger.value("long", -42)
        self.assertEqual(int(val), -42)
        self.assertEqual(str(gdb.lookup_type("long")), str(val.type))

        val = debugger.value("float", 42.42)
        self.assertEqual(float(val), 42.41999816894531)
        self.assertEqual(str(gdb.lookup_type("float")), str(val.type))

        val = debugger.value("double", 42.42)
        self.assertEqual(float(val), 42.42)
        self.assertEqual(str(gdb.lookup_type("double")), str(val.type))

        val = debugger.value("enum enumeration", 1)
        self.assertEqual(int(val), 1)
        self.assertEqual(str(gdb.lookup_type("enum enumeration").target()), str(val.type))

    def test_basic_pointer_types(self):
        val = debugger.pointer(debugger.value("char", "c"))
        self.assertEqual(str(gdb.lookup_type("char").pointer()), str(val.type))
        self.assertEqual(chr(val.dereference()), "c")

        val = debugger.pointer(debugger.value("unsigned int", 42))
        self.assertEqual(str(gdb.lookup_type("unsigned int").pointer()), str(val.type))
        self.assertEqual(int(val.dereference()), 42)

        val = debugger.pointer(debugger.value("short", -42))
        self.assertEqual(str(gdb.lookup_type("short").pointer()), str(val.type))
        self.assertEqual(int(val.dereference()), -42)

        val = debugger.pointer(debugger.value("int", -42))
        self.assertEqual(str(gdb.lookup_type("int").pointer()), str(val.type))
        self.assertEqual(int(val.dereference()), -42)

        val = debugger.pointer(debugger.value("long", -42))
        self.assertEqual(str(gdb.lookup_type("long").pointer()), str(val.type))
        self.assertEqual(int(val.dereference()), -42)

        val = debugger.pointer(debugger.value("float", 42.42))
        self.assertEqual(str(gdb.lookup_type("float").pointer()), str(val.type))
        self.assertEqual(float(val.dereference()), 42.41999816894531)

        val = debugger.pointer(debugger.value("double", 42.42))
        self.assertEqual(str(gdb.lookup_type("double").pointer()), str(val.type))
        self.assertEqual(float(val.dereference()), 42.42)

        val = debugger.pointer(debugger.value("enum enumeration", 1))
        self.assertEqual(str(gdb.lookup_type("enum enumeration").target().pointer()), str(val.type))
        self.assertEqual(int(val.dereference()), 1)

    def test_arrays(self):
        array = [1, 2, 3, 4, 42]
        val = debugger.value("int", array)
        self.assertEqual(str(gdb.lookup_type("int").array(len(array) - 1)), str(val.type))
        val = list(ccorrect.gdb_array_iter(val))

        self.assertEqual(len(val), len(array))
        for i, elem in enumerate(val):
            self.assertEqual(int(elem), array[i])

        array = ["h", "e", "l", "l", "o"]
        val = debugger.value("char", array)
        self.assertEqual(str(gdb.lookup_type("char").array(len(array) - 1)), str(val.type))
        val = list(ccorrect.gdb_array_iter(val))

        self.assertEqual(len(val), len(array))
        for i, elem in enumerate(val):
            self.assertEqual(chr(elem), array[i])

    def test_array_pointer(self):
        array = [0, 1, 2, 42]
        val = debugger.pointer(debugger.value("int", array))
        for i in range(4):
            self.assertEqual(int(val.dereference()[i]), array[i])

    def test_strings(self):
        string = "hello"

        val = debugger.string("hello")
        val_len = 0
        while val[val_len] != 0:
            val_len += 1
        self.assertEqual(val_len, len(string))

        for i in range(val_len + 1):
            if i == val_len:
                self.assertEqual(chr(val[i]), '\0')
            else:
                self.assertEqual(chr(val[i]), string[i])

        val = debugger.pointer(debugger.value("str_struct", {"value": 42, "name": "Hello there!"}))
        str_struct_name_len = debugger.function("str_struct_name_len")
        ret = str_struct_name_len(val)
        self.assertEqual(ret, 12)

    def test_multidimensional_arrays(self):
        array = [[1, 2], [3, 4], [5, 6], [7, 8]]
        val = debugger.value("int", array)
        val = list(ccorrect.gdb_array_iter(val))

        self.assertEqual(len(val), len(array))
        for i, elem in enumerate(val):
            elem = list(ccorrect.gdb_array_iter(elem))

            self.assertEqual(len(elem), len(array[i]))
            for j, inner_elem in enumerate(elem):
                self.assertEqual(int(inner_elem), array[i][j])

        array = [[[1, 2, 3], [4, 5, 6]], [[7, 8, 9], [10, 11, 12]], [[1, 2, 3], [4, 5, 6]], [[7, 8, 9], [10, 11, 12]]]
        val = debugger.value("int", array)
        val = list(ccorrect.gdb_array_iter(val))

        self.assertEqual(len(val), len(array))
        for i, elem in enumerate(val):
            elem = list(ccorrect.gdb_array_iter(elem))

            self.assertEqual(len(elem), len(array[i]))
            for j, inner_elem in enumerate(elem):
                inner_elem = list(ccorrect.gdb_array_iter(inner_elem))

                self.assertEqual(len(inner_elem), len(array[i][j]))
                for k, innermost_elem in enumerate(inner_elem):
                    self.assertEqual(int(innermost_elem), array[i][j][k])

    def test_union(self):
        size = gdb.lookup_type("test_union").sizeof

        value = debugger.value("test_union", {"c": 8})
        self.assertEqual(value.type.sizeof, size)
        self.assertEqual(value["c"], 8)
        self.assertEqual(value["t"]["c"], 8)
        self.assertEqual(value["t"]["i"], 0)
        self.assertEqual(value["l"], 8)

        value = debugger.value("test_union", {"t": {"c": 1, "i": 2}, "l": 421})
        self.assertEqual(value.type.sizeof, size)
        self.assertEqual(value["c"], -91)
        self.assertEqual(value["t"]["c"], -91)
        self.assertEqual(value["t"]["i"], 0)
        self.assertEqual(value["l"], 421)

        value = debugger.value("test_union", {"l": 8, "t": {"c": 1, "i": 2}})
        self.assertEqual(value.type.sizeof, size)
        self.assertEqual(value["c"], 1)
        self.assertEqual(value["t"]["c"], 1)
        self.assertEqual(value["t"]["i"], 2)
        self.assertEqual(value["l"], 8589934593)

    def test_struct(self):
        node_struct = {"value": 4, "next": None}
        val = debugger.value("node", node_struct)
        self.assertEqual(val["value"], node_struct["value"])
        self.assertEqual(val["next"], 0)

    def test_packed_struct(self):
        struct = {"c": 'a', "i": 5}
        val = debugger.value("test_struct", struct)
        val_packed = debugger.value("test_struct_packed", struct)

        self.assertEqual(chr(val["c"]), 'a')
        self.assertEqual(val["i"], 5)

        self.assertEqual(chr(val_packed["c"]), 'a')
        self.assertEqual(val_packed["i"], 5)

        gdb.set_convenience_variable("val", val)
        gdb.set_convenience_variable("val_packed", val_packed)

        self.assertGreater(gdb.parse_and_eval("sizeof($val)"), 5)
        self.assertEqual(gdb.parse_and_eval("sizeof($val_packed)"), 5)

    def test_nested_struct(self):
        node_struct = {"value": 4, "next": {"value": 5, "next": None}}
        val = debugger.value("node_ext", node_struct)
        self.assertEqual(val["value"], node_struct["value"])
        self.assertEqual(val["next"]["value"], node_struct["next"]["value"])
        self.assertEqual(val["next"]["next"], 0)

    def test_struct_pointer(self):
        node_struct = {"value": 4, "next": {"value": 5, "next": None}}
        val = debugger.value("node_ext", node_struct)
        val = debugger.pointer(val).dereference()
        self.assertEqual(val["value"], node_struct["value"])
        self.assertEqual(val["next"]["value"], node_struct["next"]["value"])
        self.assertEqual(val["next"]["next"], 0)

    def test_struct_nested_array(self):
        # nested 1D array
        array = [1, 2, 3, 4]
        node_struct = {"value": 4, "next": array}
        val = debugger.value("node_array", node_struct)

        self.assertEqual(val["value"], node_struct["value"])
        val = list(ccorrect.gdb_array_iter(val["next"]))

        self.assertEqual(len(val), len(array))
        for i, elem in enumerate(val):
            self.assertEqual(int(elem), array[i])

        # nested 2D array
        array = [[1, 2], [3, 4], [5, 6], [7, 8]]
        node_struct = {"value": 4, "next": array}
        val = debugger.value("node_array2d", node_struct)

        self.assertEqual(val["value"], node_struct["value"])
        val = list(ccorrect.gdb_array_iter(val["next"]))

        self.assertEqual(len(val), len(array))
        for i, elem in enumerate(val):
            elem = list(ccorrect.gdb_array_iter(elem))

            self.assertEqual(len(elem), len(array[i]))
            for j, inner_elem in enumerate(elem):
                self.assertEqual(int(inner_elem), array[i][j])

    def test_struct_flexible_array(self):
        test_flexible = debugger.function("test_flexible")

        val = debugger.value("struct_flexible_array", {"size": 3, "array": [11, 22, 33]})
        self.assertEqual(test_flexible(debugger.pointer(val)), sum([11, 22, 33]))

        val = debugger.value("struct_nested_flexible_array", {"value": 42, "nested": {"size": 5, "array": [1, 2, 3, 4, -1]}})
        self.assertEqual(test_flexible(debugger.pointer(val["nested"])), sum([1, 2, 3, 4, -1]))

    def test_nested_struct_pointer(self):
        node_struct = {"value": 4, "next": {"value": 5, "next": None}}
        val = debugger.value("node", node_struct)
        self.assertEqual(val["value"], node_struct["value"])
        self.assertGreaterEqual(val["next"], 0)
        nested_node_struct = val["next"].dereference()
        self.assertEqual(nested_node_struct["value"], node_struct["next"]["value"])
        self.assertEqual(nested_node_struct["next"], 0)

    def test_circular_struct(self):
        # manually create circular struct using pointers of previously allocated values
        tail = debugger.pointer(debugger.value("node", {"value": 6, "next": None}))
        middle = debugger.pointer(debugger.value("node", {"value": 5, "next": ccorrect.Ptr(tail)}))
        head = debugger.pointer(debugger.value("node", {"value": 4, "next": ccorrect.Ptr(middle)}))

        gdb.parse_and_eval(f"((node *) {tail})->next = {head}")

        self.assertEqual(head["value"], 4)
        self.assertEqual(int(head["next"]), int(middle))

        self.assertEqual(middle["value"], 5)
        self.assertEqual(int(middle["next"]), int(tail))

        self.assertEqual(tail["value"], 6)
        self.assertEqual(int(tail["next"]), int(head))

    def test_array_of_structs(self):
        array = [{"value": 4, "next": None}, {"value": 5, "next": {"value": 42, "next": None}}, {"value": 6, "next": None}]
        val = debugger.value("node", array)

        self.assertEqual(len(array), len(list(ccorrect.gdb_array_iter(val))))

        self.assertEqual(val[0]["value"], 4)
        self.assertEqual(val[0]["next"], 0)

        self.assertEqual(val[1]["value"], 5)
        self.assertGreater(val[1]["next"], 0)

        inner_struct = val[1]["next"].dereference()
        self.assertEqual(inner_struct["value"], 42)
        self.assertEqual(inner_struct["next"], 0)

        self.assertEqual(val[2]["value"], 6)
        self.assertEqual(val[2]["next"], 0)

    def test_pointer_from_value(self):
        val = debugger.value("node", {"value": 4, "next": None})
        ptr = debugger.pointer(val)
        ptr_ptr = debugger.pointer(ptr)

        self.assertEqual(str(val.type), "node")
        self.assertEqual(val["value"], 4)

        self.assertEqual(str(ptr.type), "node *")
        self.assertEqual(str(ptr.dereference().type), "node")
        self.assertEqual(ptr.dereference()["value"], 4)

        self.assertEqual(str(ptr_ptr.type), "node **")
        self.assertEqual(str(ptr_ptr.dereference().type), "node *")
        self.assertEqual(ptr_ptr.dereference().dereference()["value"], 4)
