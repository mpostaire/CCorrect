import gdb
import sys
import os
from contextlib import contextmanager
from ccorrect._values import ValueBuilder, FuncWrapper, ensure_none_debugging, ensure_self_debugging


class FuncStats:
    def __init__(self, name: str):
        self.name = name
        self.called = 0
        self.args = []
        self.returns = []

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
            return [symbol.value(frame) for symbol in block if symbol.is_argument]
        except RuntimeError:
            return None

    def set_finish_breakpoint(self):
        try:
            FuncFinishBreakpoint(self.debugger.stats, self.location)
        except ValueError:
            # print(f"Cannot set finish breakpoint for '{self.location}'", file=sys.stderr)
            pass

    def stop(self):
        args = self.get_args()
        stats = self.debugger.stats

        if self.location == "free":
            address = int(args[0])
            if address in self.debugger.allocated_addresses:
                self.debugger.allocated_addresses.remove(address)

        if self.watch:
            # if we can't set finish breakpoint, it's because the frame must be a dummy frame (meaning it's called by gdb so we don't want to keep stats of it)
            if self.failure is None:
                self.set_finish_breakpoint()

            stats[self.location].called += 1
            stats[self.location].args.append(args)

        if self.failure is not None:
            if "when" in self.failure and self.failure["when"] is not None:
                if "_when_count" not in self.failure:
                    self.failure["_when_count"] = 0
                    when_count = 0
                else:
                    when_count = self.failure["_when_count"]

                self.failure["_when_count"] += 1

                if when_count in self.failure["when"]:
                    self.failure["when"].remove(when_count)
                else:
                    if self.watch:
                        self.set_finish_breakpoint()
                    return False

            if "errno" in self.failure and self.failure["errno"] is not None:
                try:
                    gdb.set_convenience_variable("__CCorrect_errno", self.failure["errno"])
                    gdb.execute("set errno = $__CCorrect_errno")
                except gdb.error:
                    print("can't set errno", file=sys.stderr)

            if "ret_args" in self.failure and self.failure["ret_args"] is not None:
                inferior = gdb.selected_inferior()
                for i, new in self.failure["ret_args"].items():
                    old = args[i]
                    if old.type.strip_typedefs().unqualified().code != gdb.TYPE_CODE_PTR:
                        continue

                    new_bytes = inferior.read_memory(new, new.type.sizeof).tobytes(order="A")
                    inferior.write_memory(old, new_bytes, new.type.sizeof)

                    if self.watch:
                        stats[self.location].args[-1][i] = new

            if "return" in self.failure and self.failure["return"] is not None:
                gdb.set_convenience_variable("__CCorrect_return_var", self.failure["return"])
                if self.watch:
                    stats[self.location].returns.append(gdb.convenience_variable('__CCorrect_return_var'))
                gdb.execute("return $__CCorrect_return_var")
            else:
                if self.watch:
                    stats[self.location].returns.append(None)
                gdb.execute("return")

        return False


class Debugger(ValueBuilder):
    def __init__(self, program, backtrace_max_depth=8, save_output=True, asan_detect_leaks=False):
        super().__init__()
        self.stats = {}
        self.backtrace_max_depth = backtrace_max_depth
        self._program = program
        self._asan_detect_leaks = asan_detect_leaks
        self._save_output = save_output
        self.__breakpoints = {}

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
        # TODO functions can contain gdb.Value
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
            
            if func not in self.stats:
                self.stats[func] = FuncStats(func)

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
    def fail(self, function, retval=None, ret_args=None, errno=None, when=None):
        """
        This cannot fail function calls that are directly called by the debugger/gdb
        """
        # TODO function can be a gdb.Value
        failure = {}

        if retval is not None:
            if not isinstance(retval, gdb.Value):
                retval = self.value(gdb.parse_and_eval(function).type.target(), retval)
            failure["return"] = retval

        if errno is not None:
            assert isinstance(errno, int) or (isinstance(errno, gdb.Value) and str(errno.type.strip_typedefs().unqualified()) == "int")
            failure["errno"] = errno

        if ret_args is not None:
            assert isinstance(ret_args, dict)

            func = gdb.parse_and_eval(function)
            parsed_ret_args = {}
            func_type_fields = func.type.fields()
            arg_types = [(func_type_fields[i].type, i) for i in ret_args.keys()]
            for arg, (type, i) in zip(ret_args.values(), arg_types):
                if isinstance(arg, FuncWrapper):
                    arg = arg._value
                elif not isinstance(arg, gdb.Value):
                    arg = self.value(type, arg)
                parsed_ret_args[i] = arg

            failure["ret_args"] = parsed_ret_args

        if when is not None:
            failure["when"] = set(when)

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
    def start(self, timeout=0):
        self.stats.clear()

        # enable debuginfod if possible
        try:
            gdb.execute("set debuginfod enabled on")
        except gdb.error:
            print("debuginfod cannot be enabled", file=sys.stderr)

        gdb.events.stop.connect(self.__stop_event_handler)
        gdb.events.exited.connect(self.__exited_event_handler)

        # gdb.execute(f"set environment ASAN_OPTIONS=log_path=asan_log:detect_leaks={int(self._asan_detect_leaks)}:stack_trace_format='[]'")
        gdb.execute(f"set environment ASAN_OPTIONS=log_path=asan_log:detect_leaks={int(self._asan_detect_leaks)}")
        gdb.execute("set environment TSAN_OPTIONS=log_path=tsan_log")
        gdb.execute(f"file {self._program}")  # load program
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
            self.__detach_and_wait_leak_sanitizer()
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
    def thread_count(self):
        return int(gdb.convenience_variable("_inferior_thread_count"))

    def __get_breakpoint(self, function):
        if function == "free":
            return self.__free_breakpoint
        if function in self.__breakpoints:
            return self.__breakpoints[function]
        return None

    def __detach_and_wait_leak_sanitizer(self):
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
            return {symbol.name: (symbol.value(frame), symbol.is_argument) for symbol in block if symbol.is_variable}
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
