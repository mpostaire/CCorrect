import gdb
import sys
import os
from contextlib import contextmanager
from ccorrect._parser import FuncCallParser
from ccorrect._values import ValueBuilder


class FuncStats:
    def __init__(self, name: str, called: int, args: list, returns: list):
        self.name = name
        self.called = called
        self.args = args
        self.returns = returns

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', called={self.called}, args={self.args}, returns={self.returns})"


class FuncFinishBreakpoint(gdb.FinishBreakpoint):
    def __init__(self, stats, func_location, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stats = stats
        self.func_location = func_location

    def stop(self):
        self.stats[self.func_location].returns.append(self.return_value)
        return False


class FuncBreakpoint(gdb.Breakpoint):
    def __init__(self, debugger, watch, failure, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.debugger = debugger
        self.failure = failure
        self.watch = watch

    def get_args(self):
        try:
            frame = gdb.newest_frame()
            block = frame.block()
            return tuple(symbol.value(frame) for symbol in block if symbol.is_argument)
        except RuntimeError:
            return None

    def stop(self):
        args = self.get_args()

        if self.location == "free":
            address = int(args[0])
            if address in self.debugger.allocated_addresses:
                self.debugger.allocated_addresses.remove(address)

        if self.watch:
            # if we can't set finish breakpoint, it's because the frame must be a dummy frame (meaning it's called by gdb so we don't want to keep stats of it)
            if self.failure is None:
                try:
                    FuncFinishBreakpoint(self.debugger.stats, self.location)
                except ValueError:
                    # print(f"Cannot set finish breakpoint for '{self.location}'", file=sys.stderr)
                    pass

            if self.location not in self.debugger.stats:
                self.debugger.stats[self.location] = FuncStats(self.location, 1, [args], [])
            else:
                self.debugger.stats[self.location].called += 1
                self.debugger.stats[self.location].args.append(args)

        if self.failure is not None:
            if "errno" in self.failure and self.failure["errno"] is not None:
                try:
                    gdb.set_convenience_variable("__CCorrect_errno", self.failure["errno"])
                    gdb.execute("set errno = $__CCorrect_errno")
                except gdb.error:
                    print("can't set errno", file=sys.stderr)

            if "return" in self.failure and self.failure["return"] is not None:
                gdb.set_convenience_variable("__CCorrect_return_var", self.failure["return"])
                if self.watch:
                    self.debugger.stats[self.location].returns.append(gdb.convenience_variable('__CCorrect_return_var'))
                gdb.execute("return $__CCorrect_return_var")
            else:
                gdb.execute("return")

        return False


class Debugger(ValueBuilder):
    def __init__(self, program, source_files=None, banned_functions=None, save_output=True, asan_detect_leaks=False):
        super().__init__()
        self.stats = {}
        self._program = program
        self._asan_detect_leaks = asan_detect_leaks
        self._save_output = save_output
        self.__sources_func_calls = set()
        self.__breakpoints = {}

        if source_files:
            for f in source_files:
                func_calls = FuncCallParser(f).parse()
                if func_calls:
                    self.__sources_func_calls.update(func_calls)

        for f in self.__sources_func_calls:
            if f in banned_functions:
                print(f"'{f}' is a banned function", file=sys.stderr)
                # TODO THIS DOESN'T WORK ANYMORE... (make unittests)
                # raise RuntimeError(f"'{self.location}' is a banned function")
                gdb.execute("quit 1")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.finish()

    @contextmanager
    def watch(self, functions):
        """
        This cannot watch function calls that are directly called by the debugger/gdb
        """
        if gdb.convenience_variable("__CCorrect_debugging") != id(self):
            raise RuntimeError("Another program is already being run by gdb")

        if not isinstance(functions, (list, tuple)):
            functions = [functions]

        cleanup_breakpoints = []
        cleanup_watch = []
        for func in functions:
            bp = self.__get_breakpoint(func)
            if bp is None:
                # create a new watch breakpoint if there wasn't one at this location
                bp = FuncBreakpoint(self, True, None, func)
                self.__breakpoints[func] = bp
                cleanup_breakpoints.append(bp)
            elif not bp.watch:
                # start watching if there is already a breakpoint at this location but it isn't watching
                bp.watch = True
                cleanup_watch.append(bp)

        try:
            yield
        finally:
            for bp in cleanup_watch:
                bp.watch = False
            for bp in cleanup_breakpoints:
                del self.__breakpoints[bp.location]
                bp.delete()

    @contextmanager
    # def fail(self, function, retval, args=None, errno=None, when=None):
    def fail(self, function, retval):
        if gdb.convenience_variable("__CCorrect_debugging") != id(self):
            raise RuntimeError("Another program is already being run by gdb")

        # TODO third argument that is a set of numbers: {1, 2, 5} (1st, 2nd and 5th calls should fail, other shouldn't)
        # TODO set errno
        # TODO add unittests for errno and when
        failure = {"return": retval}
        # if errno is not None:
        #     assert isinstance(errno, int) or (isinstance(errno, gdb.Value) and str(errno.type().strip_typedefs()) == "int")
        #     failure["errno"] = errno
        # if args is not None:
        #     assert isinstance(args, (list, tuple))
        #     failure["args"] = args
        # if when is not None:
        #     failure["when"] = set(when)

        bp = self.__get_breakpoint(function)
        old_failure = None
        cleanup_breakpoint = False
        if bp is None:
            # create a new fail breakpoint if there wasn't one at this location
            bp = FuncBreakpoint(self, False, failure, function)
            self.__breakpoints[function] = bp
            cleanup_breakpoint = True
        else:
            # there already is a breakpoint at this location so we set it a new failure, backing up the old one, if any, to restore later
            old_failure = bp.failure
            bp.failure = failure

        try:
            yield
        finally:
            bp.failure = old_failure  # put back old failure in the breakpoint
            if cleanup_breakpoint:
                del self.__breakpoints[bp.location]
                bp.delete()

    def start(self, timeout=0):
        if gdb.convenience_variable("__CCorrect_debugging") is not None:
            raise RuntimeError("Another program is already being run by gdb")

        self.stats.clear()

        # enable debuginfod if possible
        try:
            gdb.execute("set debuginfod enabled on")
        except gdb.error:
            print("debuginfod cannot be enabled", file=sys.stderr)

        gdb.events.stop.connect(self.__stop_event_handler)
        gdb.events.exited.connect(self.__exited_event_handler)

        gdb.execute(f"set environment ASAN_OPTIONS=log_path=asan_log:detect_leaks={1 if self._asan_detect_leaks else 0}")
        gdb.execute(f"file {self._program}")  # load program
        gdb.execute(f"start {'1> stdout.txt 2> stderr.txt' if self._save_output else ''}")

        # create breakpoint after start command to avoid the address sanitizer setup
        self.__free_breakpoint = FuncBreakpoint(self, False, None, "free")
        self.__free_breakpoint.watch = False

        if timeout > 0:
            gdb.execute("handle SIGALRM stop")  # tell gdb to stop when the inferior receives a SIGALRM
            gdb.parse_and_eval(f"(unsigned int) alarm({timeout})")

        gdb.set_convenience_variable("__CCorrect_debugging", id(self))

        return gdb.selected_inferior().pid

    def finish(self, free_allocated_values=True):
        if gdb.convenience_variable("__CCorrect_debugging") != id(self):
            raise RuntimeError("Another program is already being run by gdb")

        try:
            if free_allocated_values:
                self.free_allocated_values()
            self.__wait_leak_sanitizer()
        except gdb.error:
            pass

        gdb.events.stop.disconnect(self.__stop_event_handler)
        gdb.events.exited.disconnect(self.__exited_event_handler)

        gdb.execute("file")  # discard any info on the loaded program and the symbol table
        gdb.execute("delete")  # delete all breakpoints
        self.__breakpoints.clear()
        self.__free_breakpoint = None
        gdb.set_convenience_variable("__CCorrect_debugging", None)

    def call(self, funcname, args=None):
        if gdb.convenience_variable("__CCorrect_debugging") != id(self):
            raise RuntimeError("Another program is already being run by gdb")

        parsed_args = []
        func = gdb.parse_and_eval(funcname)
        if args is not None:
            arg_types = [field.type for field in func.type.fields()]
            for arg, type in zip(args, arg_types):
                if not isinstance(arg, gdb.Value):
                    arg = self.value(type, arg)
                parsed_args.append(arg)

        return func(*parsed_args)

    def thread_count(self):
        if gdb.convenience_variable("__CCorrect_debugging") != id(self):
            raise RuntimeError("Another program is already being run by gdb")
        return int(gdb.convenience_variable("_inferior_thread_count"))

    def __stack_variables(self):
        try:
            frame = gdb.newest_frame()
            block = frame.block()
            return {symbol.name: symbol.value(frame) for symbol in block}
        except RuntimeError:
            return None

    def __get_breakpoint(self, function):
        if function == "free":
            return self.__free_breakpoint
        if function in self.__breakpoints:
            return self.__breakpoints[function]
        return None

    def __wait_leak_sanitizer(self):
        # detach inferior process to allow the leak sanitizer to work
        # https://stackoverflow.com/a/54373833
        pid = gdb.selected_inferior().pid
        gdb.execute("detach")
        # waiting for the leak sanitizer checks to complete
        os.waitpid(pid, 0)

    def __stop_event_handler(self, event):
        # this is needed to avoid parallel exec of the handler
        # https://stackoverflow.com/questions/25410568/continue-after-signal-with-a-python-script-in-gdb
        gdb.execute("set scheduler-locking on")

        # the breakpoint on main() created by the gdb start command will call this handler so we ignore all events that aren't signals
        # this handler won't be called by our own FuncBreakpoint and FuncFinishBreakpoint because they never stop (their stop method always return False)
        if not isinstance(event, gdb.SignalEvent):
            gdb.execute("set scheduler-locking off")
            return

        if event.stop_signal == "SIGALRM":
            return
        with open("crash_log.txt", "w") as f:
            f.write(f"ERROR: Program received signal {event.stop_signal}\n")
            f.write(gdb.execute('backtrace', to_string=True))
            stack_variables = [f"{name} = ({value.type}) {value}" for name, value in self.__stack_variables().items()]
            # TODO print var: name = (type) value (auto dereference value if it is a pointer? what about long nested structs? and circular references?)
            if stack_variables:
                stack_variables_str = "\n    ".join(stack_variables)
            else:
                stack_variables_str = "no variables"
            # TODO print stack variables for all stack (if crash happens in a stdlib function, it will show only the stack variables of
            #       the stdlib's function stack variables and not the ones of the student code... --> print all stack variables until dummy frame)
            # ---> Test if writing output of gdb.execute("backtrace -full -frame-arguments all", to_string=True) looks good
            #       this can then be used with asan_log (there will be 2 backtraces asan and gdb)
            f.write(f"\n{'=' * 65}\nStack variables at the moment of the crash:\n    {stack_variables_str}\n")

        print(f"RECEIVED SIGNAL: {event.stop_signal} (check 'crash_log.txt' for more info)", file=sys.stderr)

    def __exited_event_handler(self, event):
        print(f"event type: exit ({event})")
        if hasattr(event, 'exit_code'):
            print(f"exit code: {event.exit_code}")
        else:
            print("exit code not available")
