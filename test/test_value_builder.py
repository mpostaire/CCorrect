from ccorrect.debugger import Debugger
import ccorrect.values as cval
import unittest


class TestValueBuilder(unittest.TestCase):
    def tearDown(self):
        cval.free_allocated_values()

    def test_basic_types(self):
        val = cval.value("char", "c")
        self.assertEqual(chr(val), "c")

        val = cval.value("unsigned int", 42)
        self.assertEqual(int(val), 42)

        val = cval.value("short", -42)
        self.assertEqual(int(val), -42)

        val = cval.value("int", -42)
        self.assertEqual(int(val), -42)

        val = cval.value("long", -42)
        self.assertEqual(int(val), -42)

        val = cval.value("float", 42.42)
        self.assertEqual(float(val), 42.41999816894531)

        val = cval.value("double", 42.42)
        self.assertEqual(float(val), 42.42)

    def test_basic_allocated_types(self):
        val = cval.value_allocated("char", "c")
        self.assertEqual(chr(val.dereference()), "c")

        val = cval.value_allocated("unsigned int", 42)
        self.assertEqual(int(val.dereference()), 42)

        val = cval.value_allocated("short", -42)
        self.assertEqual(int(val.dereference()), -42)

        val = cval.value_allocated("int", -42)
        self.assertEqual(int(val.dereference()), -42)

        val = cval.value_allocated("long", -42)
        self.assertEqual(int(val.dereference()), -42)

        val = cval.value_allocated("float", 42.42)
        self.assertEqual(float(val.dereference()), 42.41999816894531)

        val = cval.value_allocated("double", 42.42)
        self.assertEqual(float(val.dereference()), 42.42)

    def test_arrays(self):
        array = [1, 2, 3, 4, 42]
        val = cval.value("int", array)
        val = list(cval.gdb_array_iterator(val))

        self.assertEqual(len(val), len(array))
        for i, elem in enumerate(val):
            self.assertEqual(int(elem), array[i])

        array = ["h", "e", "l", "l", "o"]
        val = cval.value("char", array)
        val = list(cval.gdb_array_iterator(val))

        self.assertEqual(len(val), len(array))
        for i, elem in enumerate(val):
            self.assertEqual(chr(elem), array[i])

    def test_allocated_arrays(self):
        array = [0, 1, 2, 42]
        val = cval.value_allocated("int", array)
        for i in range(4):
            self.assertEqual(int(val[i]), array[i])

    def test_strings(self):
        # TODO check that it's null character terminated!!!!
        string = "hello"

        val = cval.string("hello")
        for i, c in enumerate(string):
            self.assertEqual(chr(val[i]), c)

        val = cval.string_allocated(string)
        for i, c in enumerate(string):
            self.assertEqual(chr(val[i]), c)

    def test_multidimensional_arrays(self):
        array = [[1, 2], [3, 4], [5, 6], [7, 8]]
        val = cval.value("int", array)
        val = list(cval.gdb_array_iterator(val))

        self.assertEqual(len(val), len(array))
        for i, elem in enumerate(val):
            elem = list(cval.gdb_array_iterator(elem))

            self.assertEqual(len(elem), len(array[i]))
            for j, inner_elem in enumerate(elem):
                self.assertEqual(int(inner_elem), array[i][j])

        array = [[[1, 2, 3], [4, 5, 6]], [[7, 8, 9], [10, 11, 12]], [[1, 2, 3], [4, 5, 6]], [[7, 8, 9], [10, 11, 12]]]
        val = cval.value("int", array)
        val = list(cval.gdb_array_iterator(val))

        self.assertEqual(len(val), len(array))
        for i, elem in enumerate(val):
            elem = list(cval.gdb_array_iterator(elem))

            self.assertEqual(len(elem), len(array[i]))
            for j, inner_elem in enumerate(elem):
                inner_elem = list(cval.gdb_array_iterator(inner_elem))

                self.assertEqual(len(inner_elem), len(array[i][j]))
                for k, innermost_elem in enumerate(inner_elem):
                    self.assertEqual(int(innermost_elem), array[i][j][k])

    def test_struct(self):
        node_struct = {"value": 4, "next": None}
        val = cval.value("node", node_struct)
        self.assertEqual(val["value"], node_struct["value"])
        self.assertEqual(val["next"], 0)

    def test_nested_struct(self):
        node_struct = {"value": 4, "next": {"value": 5, "next": None}}
        val = cval.value("node_ext", node_struct)
        self.assertEqual(val["value"], node_struct["value"])
        self.assertEqual(val["next"]["value"], node_struct["next"]["value"])
        self.assertEqual(val["next"]["next"], 0)

    def test_allocated_struct(self):
        node_struct = {"value": 4, "next": {"value": 5, "next": None}}
        val = cval.value_allocated("node_ext", node_struct)
        val = val.dereference()
        self.assertEqual(val["value"], node_struct["value"])
        self.assertEqual(val["next"]["value"], node_struct["next"]["value"])
        self.assertEqual(val["next"]["next"], 0)

    def test_struct_nested_array(self):
        # nested 1D array
        array = [1, 2, 3, 4]
        node_struct = {"value": 4, "next": array}
        val = cval.value("node_array", node_struct)

        self.assertEqual(val["value"], node_struct["value"])
        val = list(cval.gdb_array_iterator(val["next"]))

        self.assertEqual(len(val), len(array))
        for i, elem in enumerate(val):
            self.assertEqual(int(elem), array[i])

        # nested 2D array
        array = [[1, 2], [3, 4], [5, 6], [7, 8]]
        node_struct = {"value": 4, "next": array}
        val = cval.value("node_array2d", node_struct)

        self.assertEqual(val["value"], node_struct["value"])
        val = list(cval.gdb_array_iterator(val["next"]))

        self.assertEqual(len(val), len(array))
        for i, elem in enumerate(val):
            elem = list(cval.gdb_array_iterator(elem))

            self.assertEqual(len(elem), len(array[i]))
            for j, inner_elem in enumerate(elem):
                self.assertEqual(int(inner_elem), array[i][j])

    def test_nested_struct_pointer(self):
        node_struct = {"value": 4, "next": {"value": 5, "next": None}}
        val = cval.value("node", node_struct)
        self.assertEqual(val["value"], node_struct["value"])
        self.assertGreaterEqual(val["next"], 0)
        nested_node_struct = val["next"].dereference()
        self.assertEqual(nested_node_struct["value"], node_struct["next"]["value"])
        self.assertEqual(nested_node_struct["next"], 0)

    def test_circular_struct(self):
        # manually create circular struct using pointers of previously allocated values
        tail = cval.value_allocated("node", {"value": 6, "next": None})
        middle = cval.value_allocated("node", {"value": 5, "next": cval.Ptr(tail)})
        head = cval.value_allocated("node", {"value": 4, "next": cval.Ptr(middle)})

        gdb.parse_and_eval(f"((node *) {tail})->next = {head}")

        self.assertEqual(head["value"], 4)
        self.assertEqual(int(head["next"]), int(middle))

        self.assertEqual(middle["value"], 5)
        self.assertEqual(int(middle["next"]), int(tail))

        self.assertEqual(tail["value"], 6)
        self.assertEqual(int(tail["next"]), int(head))

    def test_array_of_structs(self):
        array = [{"value": 4, "next": None}, {"value": 5, "next": {"value": 42, "next": None}}, {"value": 6, "next": None}]
        val = cval.value("node", array)

        self.assertEqual(len(array), len(list(cval.gdb_array_iterator(val))))

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
        val = cval.value_allocated("node", {"value": 4, "next": None})
        ptr = cval.pointer(val)

        self.assertEqual(str(val.type), "struct node *")
        self.assertEqual(val["value"], 4)

        self.assertEqual(str(ptr.type), "struct node **")
        self.assertEqual(str(ptr.dereference().type), "struct node *")
        self.assertEqual(ptr.dereference()["value"], 4)

        # cannot get pointer of gdb.Value that isn't allocated on the inferior's heap 
        with self.assertRaises(gdb.error):
            val = cval.value("node", {"value": 4, "next": None})
            ptr = cval.pointer(val)


tester = Debugger()
gdb = tester.start()

unittest.main()


# # /!\ Not supported ----> doable with gdb.parse_and_eval() using malloc for the whole size of the struct and
# #                       setting manually the elements
# # node_nested_struct_array_variable = {"value": 4, "next": [1, 2, 3, 4]}
# # val = cval.value("node_variable_array", node_nested_struct_array_variable)
# # print(val)
