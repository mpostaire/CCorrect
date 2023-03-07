import gdb
import sys
import os
from ccorrect.parser import FuncCallParser
from ccorrect.values import ValueBuilder


class FuncStats:
    def __init__(self, name: str, called: int, args: list, returns: list):
        self.name = name
        self.called = called
        self.args = args
        self.returns = returns


class FuncFinishBreakpoint(gdb.FinishBreakpoint):
    def __init__(self, stats, func_location, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stats = stats
        self.func_location = func_location

    def stop(self):
        self.stats[self.func_location].returns.append(self.return_value)
        return False


class FuncBreakpoint(gdb.Breakpoint):
    def __init__(self, stats, failures, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stats = stats
        self.failures = failures

    def get_args(self):
        try:
            frame = gdb.newest_frame()
            block = frame.block()
            args = {symbol.name: symbol.value(frame) for symbol in block if symbol.is_argument}
            return args
        except RuntimeError:
            return None

    def stop(self):
        # allow force fail (don't execute function and change its return value and/or errno)

        fail = self.location in self.failures
        if not fail:
            # if we can't set finish breakpoint, it's because the frame must be a dummy frame (meaning it's called by gdb so we don't want to keep stats of it)
            try:
                FuncFinishBreakpoint(self.stats, self.location)
            except ValueError:
                # print(f"Cannot set finish breakpoint for '{self.location}'")
                return False

        args = self.get_args()

        if self.location not in self.stats:
            self.stats[self.location] = FuncStats(self.location, 1, [args], [])
        else:
            self.stats[self.location].called += 1
            self.stats[self.location].args.append(args)

        stats = self.stats[self.location]

        if fail:
            failure = self.failures[self.location]

            gdb.set_convenience_variable("__CCorrect_return_var", failure["return"])
            stats.returns.append(gdb.convenience_variable('__CCorrect_return_var'))
            gdb.execute(f"return $__CCorrect_return_var")
            # TODO handle case where errno might not be in current context
            # TODO make unit tests for failures and errno
            if "errno" in failure and failure["errno"]:
                print(f"ERRNO SET TO {failure['errno']}")
                gdb.set_convenience_variable("__CCorrect_errno", failure["errno"])
                gdb.execute(f"errno = $__CCorrect_errno")

        return False


class Debugger(ValueBuilder):
    def __init__(self, program, source_files=None, watches=None, excludes=None, banned=None, timeout=0):
        super().__init__()
        self.program = program
        self.timeout = timeout
        self.stats = {}
        self.__failures = {}
        self.__sources_func_calls = set()
        self.__watches = set()
        self.__banned = set()
        self.__is_running = False

        if source_files:
            self.__add_func_calls(source_files)
        if watches:
            self.add_watches(watches)
        if excludes:
            self.add_excludes(excludes)
        if banned:
            self.__banned.update(banned)

        self.add_watches_from_sources()

        gdb.events.stop.connect(self._stop_event_handler)
        gdb.events.exited.connect(self._exited_event_handler)

        # enable debuginfod if possible
        try:
            gdb.execute("set debuginfod enabled on")
        except gdb.error:
            print(f"debuginfod cannot be enabled", file=sys.stderr)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.finish()

    def __add_func_calls(self, source_files):
        for f in source_files:
            func_calls = FuncCallParser(f).parse()
            if func_calls:
                self.__sources_func_calls.update(func_calls)

    def add_watches_from_sources(self, source_files=None):
        if source_files is not None:
            self.__add_func_calls(source_files)

        for f in self.__sources_func_calls:
            self.__watches.add(f)

    def add_watches(self, functions):
        self.__watches.update(functions)

    def add_excludes(self, functions):
        self.__watches.difference_update(set(functions))

    def fail(self, function, retval):
        self.__failures[function] = {"return": retval}

    def stop_fail(self, function):
        del self.__failures[function]

    def start(self):
        if self.__is_running:
            return

        for f in self.__sources_func_calls:
            if f in self.__banned:
                print(f"'{f}' is a banned function", file=sys.stderr)
                gdb.execute("quit 1")

        gdb.execute(f"file {self.program}")  # load program
        gdb.execute("start")

        # create breakpoints after start command to avoid the address sanitizer setup
        for func in self.__watches:
            FuncBreakpoint(self.stats, self.__failures, func)

        if self.timeout:
            gdb.execute("handle SIGALRM stop")  # tell gdb to stop when the inferior receives a SIGALRM
            gdb.parse_and_eval(f"alarm({self.timeout})")

        self.__is_running = True
        return

    def finish(self):
        # detach inferior process to allow the leak sanitizer to work
        # https://stackoverflow.com/a/54373833
        pid = gdb.selected_inferior().pid
        gdb.execute("detach")
        # waiting for the leak sanitizer checks to complete
        os.waitpid(pid, 0)

        gdb.execute("delete")  # delete all breakpoints
        gdb.execute("file")  # discard any info on the loaded programm and the symbol table
        self.__is_running = False

    def call(self, funcname, args=None):
        parsed_args = []
        if args is not None:
            for i, arg in enumerate(args):
                # TODO if arg is not a gdb.Value, parse it using the type from the function respective arg
                var_name = f"__CCorrect_arg{i}"
                gdb.set_convenience_variable(var_name, arg)
                parsed_args.append(f"${var_name}")

        return gdb.parse_and_eval(f"{funcname}({', '.join(parsed_args)})")

    def gdb(self):
        return gdb

    def _stop_event_handler(self, event):
        # this is needed to avoid parallel exec of the handler
        # https://stackoverflow.com/questions/25410568/continue-after-signal-with-a-python-script-in-gdb
        gdb.execute("set scheduler-locking on")

        # the breakpoint on main() created by the gdb start command will call this handler so we ignore all events that aren't signals
        # this handler won't be called by our own FuncBreakpoint and FuncFinishBreakpoint because they never stop (their stop method always return False)
        if not isinstance(event, gdb.SignalEvent):
            gdb.execute("set scheduler-locking off")
            return

        print(f"GOT EVENT {event.stop_signal}", file=sys.stderr)

    def _exited_event_handler(self, event):
        print(f"event type: exit ({event})")
        if hasattr(event, 'exit_code'):
            print(f"exit code: {event.exit_code}")
        else:
            print("exit code not available")
