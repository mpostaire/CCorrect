import gdb
import sys
import os
from contextlib import contextmanager
from functools import wraps
from ccorrect._parser import FuncCallParser
from ccorrect._values import ValueBuilder

class BannedFuncError(AssertionError):
    pass


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


def ensure_self_debugging(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        current_id = gdb.convenience_variable("__CCorrect_debugging")
        if isinstance(self, TemplateArgsFuncValue):
            self_id = self.debugger._id
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


class TemplateArgsFuncValue(gdb.Value):
    def __init__(self, debugger, *args):
        super().__init__(*args)
        self.debugger = debugger

    @ensure_self_debugging
    def __call__(self, *args):
        parsed_args = []
        if args is not None:
            arg_types = [field.type for field in self.type.fields()]
            for arg, type in zip(args, arg_types):
                if not isinstance(arg, gdb.Value):
                    arg = self.debugger.value(type, arg)
                parsed_args.append(arg)

        return super().__call__(*parsed_args)


class Debugger(ValueBuilder):
    _id_counter = 0

    def __init__(self, program, backtrace_max_depth=8, save_output=True, asan_detect_leaks=False):
        super().__init__()
        self.stats = {}
        self.backtrace_max_depth = backtrace_max_depth
        self._id = Debugger._id_counter
        Debugger._id_counter += 1
        self._program = program
        self._asan_detect_leaks = asan_detect_leaks
        self._save_output = save_output
        self.__breakpoints = {}
        self.__main_source = None

    def __enter__(self):
        pid = self.start()
        return self, pid

    def __exit__(self, exc_type, exc_value, traceback):
        self.finish()

    @contextmanager
    @ensure_self_debugging
    def watch(self, functions):
        """
        This cannot watch function calls that are directly called by the debugger/gdb
        """
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
    @ensure_self_debugging
    # def fail(self, function, retval, args=None, errno=None, when=None):
    def fail(self, function, retval):
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

    @ensure_none_debugging
    def start(self, timeout=0, banned_functions=None):
        self.stats.clear()

        # enable debuginfod if possible
        try:
            gdb.execute("set debuginfod enabled on")
        except gdb.error:
            print("debuginfod cannot be enabled", file=sys.stderr)

        # gdb.execute(f"set environment ASAN_OPTIONS=log_path=asan_log:detect_leaks={int(self._asan_detect_leaks)}:stack_trace_format='[]'")
        gdb.execute(f"set environment ASAN_OPTIONS=log_path=asan_log:detect_leaks={int(self._asan_detect_leaks)}")
        gdb.execute("set environment TSAN_OPTIONS=log_path=tsan_log")
        gdb.execute(f"file {self._program}")  # load program

        try:
            self.__check_banned_functions(banned_functions)
        except BannedFuncError as e:
            gdb.execute("file")  # discard any info on the loaded program and the symbol table
            raise e

        gdb.events.stop.connect(self.__stop_event_handler)
        gdb.events.exited.connect(self.__exited_event_handler)

        gdb.execute(f"start {'1> stdout.txt 2> stderr.txt' if self._save_output else ''}")

        # create breakpoint after start command to avoid the address sanitizer setup
        self.__free_breakpoint = FuncBreakpoint(self, False, None, "free")
        self.__free_breakpoint.watch = False

        if timeout > 0:
            gdb.execute("handle SIGALRM stop")  # tell gdb to stop when the inferior receives a SIGALRM
            gdb.parse_and_eval(f"(unsigned int) alarm({timeout})")

        gdb.set_convenience_variable("__CCorrect_debugging", self._id)

        return gdb.selected_inferior().pid

    @ensure_self_debugging
    def finish(self, free_allocated_values=True):
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

    @ensure_self_debugging
    def function(self, funcname):
        return TemplateArgsFuncValue(self, gdb.parse_and_eval(funcname))

    @ensure_self_debugging
    def functions(self, funcnames):
        return tuple(TemplateArgsFuncValue(self, gdb.parse_and_eval(funcname)) for funcname in funcnames)

    @ensure_self_debugging
    def thread_count(self):
        return int(gdb.convenience_variable("_inferior_thread_count"))

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
        if not isinstance(event, gdb.SignalEvent) or event.stop_signal == "SIGALRM":
            gdb.execute("set scheduler-locking off")
            return

        with open("crash_log.txt", "w") as f:
            f.write(self.__backtrace(event.stop_signal, max_depth=self.backtrace_max_depth))

        print(f"RECEIVED SIGNAL: {event.stop_signal} (check 'crash_log.txt' for more info)", file=sys.stderr)
        gdb.execute("set scheduler-locking off")

    def __exited_event_handler(self, event):
        print(f"event type: exit ({event})")
        if hasattr(event, 'exit_code'):
            print(f"exit code: {event.exit_code}")
        else:
            print("exit code not available")

    def __check_banned_functions(self, banned_functions):
        if banned_functions is None:
            return

        if self.__main_source is None:
            sal = gdb.decode_line("main")[1][0]
            self.__main_source = sal.symtab.fullname()

        func_calls = FuncCallParser(self.__main_source).parse()
        found_banned_funcs = list(func_calls & set(banned_functions))

        if len(found_banned_funcs) == 1:
            msg = f"'{found_banned_funcs[0]}' is banned"
            raise BannedFuncError(msg)
        elif len(found_banned_funcs) > 1:
            funcnames = [f"'{funcname}'" for funcname in found_banned_funcs]
            msg = f"{', '.join(funcnames[:-1])} and {funcnames[-1]} are banned"
            raise BannedFuncError(msg)

    def __frames(self, max_depth):
        frame = gdb.newest_frame()
        for _ in range(max_depth):
            if frame is None or frame.type() == gdb.DUMMY_FRAME:
                return
            yield frame
            frame = frame.older()

        yield "--- max depth reached ---"

    def __frame_variables(self, frame=None):
        if frame is None:
            frame = gdb.newest_frame()
        try:
            block = frame.block()
            return {symbol.name: (symbol.value(frame), symbol.is_argument) for symbol in block}
        except RuntimeError:
            return None

    def __value_str(self, name, value):
        prefix = f"{name} = ({value.type})"

        try:
            value_str = value.format_string(
                raw=True,
                pretty_arrays=True,
                max_elements=16,
                pretty_structs=True,
                max_depth=16,
                unions=True
            )
        except gdb.MemoryError:
            return f"{prefix} <cannot access memory at address: {value.address}>"

        return f"{prefix} {value_str}"

    def __backtrace(self, stop_signal, max_depth):
        ret = f"ERROR: Program received signal {stop_signal}\n\n{'=' * 65}\n" \
            "Backtrace and stack variables at the moment of the crash:\n"

        for i, frame in enumerate(self.__frames(max_depth)):
            if isinstance(frame, str):
                return f"{ret} {frame}\n"

            variables = self.__frame_variables(frame) if frame is not None else None
            if variables is None:
                arg_names = ""
                variables_str = "    <no variables>"
            else:
                arg_names = ", ".join(name for name, (_, is_argument) in variables.items() if is_argument)
                variables_str = "\n".join(self.__value_str(name, value) for name, (value, _) in variables.items())
                lines = variables_str.splitlines()
                for j in range(len(lines)):
                    lines[j] = f"    {lines[j]}"
                variables_str = "\n".join(lines)

            sal = frame.find_sal()
            if sal is None or sal.symtab is None:
                filepath = ""
                line = ""
            else:
                filepath = sal.symtab.fullname()
                line = sal.line
            ret += f"#{i} {frame.name()}({arg_names}) at {filepath}:{line}\n{variables_str}\n"

        return ret
