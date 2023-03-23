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
    def __init__(self, stats, allocated_addresses, failure, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stats = stats
        self.allocated_addresses = allocated_addresses
        self.failure = failure
        self.watch = True

    def get_args(self):
        try:
            frame = gdb.newest_frame()
            block = frame.block()
            # TODO maybe it's necessary to call fetch_lazy() on each arg
            return tuple(symbol.value(frame) for symbol in block if symbol.is_argument)
        except RuntimeError:
            return None

    def stop(self):
        args = self.get_args()

        # TODO this should not remove from allocated address if free is in failures
        if self.location == "free":
            address = int(args[0])
            if address in self.allocated_addresses:
                self.allocated_addresses.remove(address)

        if self.watch:
            # if we can't set finish breakpoint, it's because the frame must be a dummy frame (meaning it's called by gdb so we don't want to keep stats of it)
            if self.failure is None:
                try:
                    FuncFinishBreakpoint(self.stats, self.location)
                except ValueError:
                    # print(f"Cannot set finish breakpoint for '{self.location}'", file=sys.stderr)
                    pass

            if self.location not in self.stats:
                self.stats[self.location] = FuncStats(self.location, 1, [args], [])
            else:
                self.stats[self.location].called += 1
                self.stats[self.location].args.append(args)

        if self.failure is not None:
            # TODO handle case where errno might not be in current context
            # TODO make unit tests for failures and errno
            if "errno" in self.failure and self.failure["errno"]:
                print(f"ERRNO SET TO {self.failure['errno']}")
                gdb.set_convenience_variable("__CCorrect_errno", self.failure["errno"])
                gdb.execute("errno = $__CCorrect_errno")

            # TODO if function doesn't return anything (void) don't do this (but it can still set errno)
            gdb.set_convenience_variable("__CCorrect_return_var", self.failure["return"])
            if self.watch:
                self.stats[self.location].returns.append(gdb.convenience_variable('__CCorrect_return_var'))
            gdb.execute("return $__CCorrect_return_var")

        return False


class Debugger(ValueBuilder):
    def __init__(self, program, source_files=None, banned_functions=None, save_output=True, asan_detect_leaks=False):
        super().__init__()
        self.stats = {}
        self._program = program
        self._asan_detect_leaks = asan_detect_leaks
        self._save_output = save_output
        self.__sources_func_calls = set()
        self.__watch_breakpoints = {}
        self.__fail_breakpoints = {}

        if source_files:
            for f in source_files:
                func_calls = FuncCallParser(f).parse()
                if func_calls:
                    self.__sources_func_calls.update(func_calls)

        for f in self.__sources_func_calls:
            if f in banned_functions:
                print(f"'{f}' is a banned function", file=sys.stderr)
                # TODO raise exception here?
                # raise RuntimeError(f"'{self.location}' is a banned function")
                gdb.execute("quit 1")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # TODO maybe here is where I can catch internal exceptions (like from banned functions)???
        #       ----> test but I don't think so...
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

        # unwatch_free = False
        cleanup_bp = []
        unwatch = []
        for func in functions:
            if func in self.__watch_breakpoints:
                # don't add a breakpoint if one was previously set at this location
                continue
            elif func in self.__fail_breakpoints:
                self.__watch_breakpoints[func] = self.__fail_breakpoints[func]
                self.__watch_breakpoints[func].watch = True
                unwatch.append(self.__watch_breakpoints[func])
            else:
                self.__watch_breakpoints[func] = FuncBreakpoint(self.stats, self.allocated_addresses, None, func)
                cleanup_bp.append(self.__watch_breakpoints[func])

        try:
            yield
        finally:
            # if unwatch_free:
            #     self.__free_breakpoint.watch = False
            for bp in cleanup_bp:
                del self.__watch_breakpoints[bp.location]
                bp.delete()
            for bp in unwatch:
                del self.__watch_breakpoints[bp.location]
                bp.watch = False

    @contextmanager
    def fail(self, function, retval, when=None):
        if gdb.convenience_variable("__CCorrect_debugging") != id(self):
            raise RuntimeError("Another program is already being run by gdb")

        # TODO third argument that is a set of numbers: {1, 2, 5} (1st, 2nd and 5th calls should fail, other shouldn't)
        if when is not None:
            when = set(when)

        old_failure = None
        cleanup_breakpoint = False
        cleanup_failure = False
        failure = {"return": retval}
        if function in self.__fail_breakpoints:
            # don't add a breakpoint if one was previously set at this location
            old_failure = self.__fail_breakpoints[function].failure
            self.__fail_breakpoints[function].failure = failure
        elif function in self.__watch_breakpoints:
            self.__fail_breakpoints[function] = self.__watch_breakpoints[function]
            old_failure = self.__fail_breakpoints[function].failure
            self.__fail_breakpoints[function].failure = failure
            cleanup_failure = True
        else:
            cleanup_failure = True
            cleanup_breakpoint = True
            self.__fail_breakpoints[function] = FuncBreakpoint(self.stats, self.allocated_addresses, failure, function)
            self.__fail_breakpoints[function].watch = False

        try:
            yield
        finally:
            if old_failure is not None:
                self.__fail_breakpoints[function].failure = old_failure
            if cleanup_breakpoint:
                self.__fail_breakpoints[function].delete()
            if cleanup_failure:
                self.__fail_breakpoints[function].failure = None
                del self.__fail_breakpoints[function]

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
        self.__free_breakpoint = FuncBreakpoint(self.stats, self.allocated_addresses, None, "free")
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
        self.__watch_breakpoints.clear()
        self.__fail_breakpoints.clear()
        self.__free_breakpoint = None
        gdb.set_convenience_variable("__CCorrect_debugging", None)

    def call(self, funcname, args=None, return_type=None):
        if gdb.convenience_variable("__CCorrect_debugging") != id(self):
            raise RuntimeError("Another program is already being run by gdb")

        parsed_args = []
        if args is not None:
            func = gdb.parse_and_eval(funcname)
            arg_types = [field.type for field in func.type.fields()]
            for i, (arg, type) in enumerate(zip(args, arg_types)):
                if not isinstance(arg, gdb.Value):
                    arg = self.value(type, arg)

                var_name = f"__CCorrect_arg{i}"
                gdb.set_convenience_variable(var_name, arg)
                parsed_args.append(f"${var_name}")

        return gdb.parse_and_eval(f"{f'({return_type})' if return_type is not None else ''}{funcname}({', '.join(parsed_args)})")

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

        # raise Exception(f"GOT EVENT {event.stop_signal}")
        # TODO find a way to make exception propagate from python while gdb is running the inferior
        #       -----> this cannot work for everything but instead of raising an error, just quit gdb wth a special return code
        print(f"GOT EVENT {event.stop_signal}", file=sys.stderr)

    def __exited_event_handler(self, event):
        print(f"event type: exit ({event})")
        if hasattr(event, 'exit_code'):
            print(f"exit code: {event.exit_code}")
        else:
            print("exit code not available")
