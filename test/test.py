import sys

sys.path.append("../")

import ccorrect
import unittest
import gdb


class TestValueBuilder(unittest.TestCase):
    def tearDown(self):
        debugger.free_allocated_values()

    def test_basic_types(self):
        val = debugger.value("char", "c")
        self.assertEqual(chr(val), "c")

        val = debugger.value("unsigned int", 42)
        self.assertEqual(int(val), 42)

        val = debugger.value("short", -42)
        self.assertEqual(int(val), -42)

        val = debugger.value("int", -42)
        self.assertEqual(int(val), -42)

        val = debugger.value("long", -42)
        self.assertEqual(int(val), -42)

        val = debugger.value("float", 42.42)
        self.assertEqual(float(val), 42.41999816894531)

        val = debugger.value("double", 42.42)
        self.assertEqual(float(val), 42.42)

    def test_basic_allocated_types(self):
        val = debugger.value_allocated("char", "c")
        self.assertEqual(chr(val.dereference()), "c")

        val = debugger.value_allocated("unsigned int", 42)
        self.assertEqual(int(val.dereference()), 42)

        val = debugger.value_allocated("short", -42)
        self.assertEqual(int(val.dereference()), -42)

        val = debugger.value_allocated("int", -42)
        self.assertEqual(int(val.dereference()), -42)

        val = debugger.value_allocated("long", -42)
        self.assertEqual(int(val.dereference()), -42)

        val = debugger.value_allocated("float", 42.42)
        self.assertEqual(float(val.dereference()), 42.41999816894531)

        val = debugger.value_allocated("double", 42.42)
        self.assertEqual(float(val.dereference()), 42.42)

    def test_arrays(self):
        array = [1, 2, 3, 4, 42]
        val = debugger.value("int", array)
        val = list(ccorrect.gdb_array_iterator(val))

        self.assertEqual(len(val), len(array))
        for i, elem in enumerate(val):
            self.assertEqual(int(elem), array[i])

        array = ["h", "e", "l", "l", "o"]
        val = debugger.value("char", array)
        val = list(ccorrect.gdb_array_iterator(val))

        self.assertEqual(len(val), len(array))
        for i, elem in enumerate(val):
            self.assertEqual(chr(elem), array[i])

    def test_allocated_arrays(self):
        array = [0, 1, 2, 42]
        val = debugger.value_allocated("int", array)
        for i in range(4):
            self.assertEqual(int(val[i]), array[i])

    def test_strings(self):
        string = "hello"

        val = debugger.string("hello")
        val_len = val.type.fields()[0].type.range()[1]
        self.assertEqual(val_len, len(string))

        for i, c in enumerate(ccorrect.gdb_array_iterator(val)):
            if i == len(string):
                self.assertEqual(chr(c), '\0')
            else:
                self.assertEqual(chr(c), string[i])

        val = debugger.string_allocated(string)
        val = val.dereference().cast(gdb.lookup_type("char").array(len(string)))
        for i, c in enumerate(ccorrect.gdb_array_iterator(val)):
            if i == len(string):
                self.assertEqual(chr(c), '\0')
            else:
                self.assertEqual(chr(c), string[i])

        val = debugger.value_allocated("str_struct", {"value": 42, "name": "Hello there!"})
        ret = debugger.call("str_struct_name_len", [val])
        self.assertEqual(ret, 12)

    def test_multidimensional_arrays(self):
        array = [[1, 2], [3, 4], [5, 6], [7, 8]]
        val = debugger.value("int", array)
        val = list(ccorrect.gdb_array_iterator(val))

        self.assertEqual(len(val), len(array))
        for i, elem in enumerate(val):
            elem = list(ccorrect.gdb_array_iterator(elem))

            self.assertEqual(len(elem), len(array[i]))
            for j, inner_elem in enumerate(elem):
                self.assertEqual(int(inner_elem), array[i][j])

        array = [[[1, 2, 3], [4, 5, 6]], [[7, 8, 9], [10, 11, 12]], [[1, 2, 3], [4, 5, 6]], [[7, 8, 9], [10, 11, 12]]]
        val = debugger.value("int", array)
        val = list(ccorrect.gdb_array_iterator(val))

        self.assertEqual(len(val), len(array))
        for i, elem in enumerate(val):
            elem = list(ccorrect.gdb_array_iterator(elem))

            self.assertEqual(len(elem), len(array[i]))
            for j, inner_elem in enumerate(elem):
                inner_elem = list(ccorrect.gdb_array_iterator(inner_elem))

                self.assertEqual(len(inner_elem), len(array[i][j]))
                for k, innermost_elem in enumerate(inner_elem):
                    self.assertEqual(int(innermost_elem), array[i][j][k])

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

        self.assertGreater(gdb.parse_and_eval(f"sizeof($val)"), 5)
        self.assertEqual(gdb.parse_and_eval(f"sizeof($val_packed)"), 5)

    def test_nested_struct(self):
        node_struct = {"value": 4, "next": {"value": 5, "next": None}}
        val = debugger.value("node_ext", node_struct)
        self.assertEqual(val["value"], node_struct["value"])
        self.assertEqual(val["next"]["value"], node_struct["next"]["value"])
        self.assertEqual(val["next"]["next"], 0)

    def test_allocated_struct(self):
        node_struct = {"value": 4, "next": {"value": 5, "next": None}}
        val = debugger.value_allocated("node_ext", node_struct)
        val = val.dereference()
        self.assertEqual(val["value"], node_struct["value"])
        self.assertEqual(val["next"]["value"], node_struct["next"]["value"])
        self.assertEqual(val["next"]["next"], 0)

    def test_struct_nested_array(self):
        # nested 1D array
        array = [1, 2, 3, 4]
        node_struct = {"value": 4, "next": array}
        val = debugger.value("node_array", node_struct)

        self.assertEqual(val["value"], node_struct["value"])
        val = list(ccorrect.gdb_array_iterator(val["next"]))

        self.assertEqual(len(val), len(array))
        for i, elem in enumerate(val):
            self.assertEqual(int(elem), array[i])

        # nested 2D array
        array = [[1, 2], [3, 4], [5, 6], [7, 8]]
        node_struct = {"value": 4, "next": array}
        val = debugger.value("node_array2d", node_struct)

        self.assertEqual(val["value"], node_struct["value"])
        val = list(ccorrect.gdb_array_iterator(val["next"]))

        self.assertEqual(len(val), len(array))
        for i, elem in enumerate(val):
            elem = list(ccorrect.gdb_array_iterator(elem))

            self.assertEqual(len(elem), len(array[i]))
            for j, inner_elem in enumerate(elem):
                self.assertEqual(int(inner_elem), array[i][j])

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
        tail = debugger.value_allocated("node", {"value": 6, "next": None})
        middle = debugger.value_allocated("node", {"value": 5, "next": ccorrect.Ptr(tail)})
        head = debugger.value_allocated("node", {"value": 4, "next": ccorrect.Ptr(middle)})

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

        self.assertEqual(len(array), len(list(ccorrect.gdb_array_iterator(val))))

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
        val = debugger.value_allocated("node", {"value": 4, "next": None})
        ptr = debugger.pointer(val)

        self.assertEqual(str(val.type), "node *")
        self.assertEqual(val["value"], 4)

        self.assertEqual(str(ptr.type), "node **")
        self.assertEqual(str(ptr.dereference().type), "node *")
        self.assertEqual(ptr.dereference()["value"], 4)

        # cannot get pointer of gdb.Value that isn't allocated on the inferior's heap 
        with self.assertRaises(AssertionError):
            val = debugger.value("node", {"value": 4, "next": None})
            ptr = debugger.pointer(val)


with ccorrect.Debugger("main") as debugger:
    unittest.main()
