import ccorrect
import gdb


flag = True

class TestStudentCode(ccorrect.TestCase):
    debugger = ccorrect.Debugger("test")

    @ccorrect.test_metadata(
        problem="calloc2",
        description="Allocated memory : test calloc2"
    )
    def test_calloc2_1(self):
        global flag
        calloc2 = self.debugger.function("calloc2")

        with self.debugger.watch("malloc"):
            ret = calloc2(16, 4)
            if ret == 0:
                flag = False
                self.fail("Erreur lors l'allocation de la mémoire.")

        if self.debugger.allocated_size() != 16 * 4:
            flag = False
            self.push_tag("not_malloc_once")
            self.fail("You allocated more memory than required.")

        if ret == 0 or not self.debugger.malloced(ret):
            flag = False

        if self.debugger.stats["malloc"].called != 1:
            flag = False
            self.push_tag("not_malloc_once")
            self.fail("Why didn't you call malloc exactly once?")

    @ccorrect.test_metadata(
        problem="calloc2",
        description="Initialised memory : test calloc2"
    )
    def test_calloc2_2(self):
        global flag
        calloc2, mallopt, malloc, free = self.debugger.functions(["calloc2", "mallopt", "malloc", "free"])
        M_PERTURB = gdb.parse_and_eval("M_PERTURB")

        m = mallopt(M_PERTURB, 42)
        if m != 1:
            cptr = malloc(10000)
            free(cptr)

        ptr = calloc2(42, 1)
        if ptr == 0:
            flag = False
            self.fail("Erreur lors l'allocation de la mémoire.")

        if ptr != 0:
            ptr = ptr.cast(gdb.lookup_type("char").pointer())
            if (ptr + 10).dereference() != 0:
                flag = False
                self.fail("You didn't initialise the allocated memory.")

    @ccorrect.test_metadata(
        problem="calloc2",
        description="Fail of malloc : test calloc2"
    )
    def test_calloc2_3(self):
        global flag
        calloc2 = self.debugger.function("calloc2")

        with self.debugger.fail("malloc", retval=ccorrect.Ptr(0)):
            ptr = calloc2(42, 42)

        if ptr != 0:
            flag = False
            self.push_tag("malloc_fail_handling")
            self.fail("Don't forget that malloc can fail sometimes.")

        if flag:
            self.push_tag("q1")


ccorrect.run_tests()
