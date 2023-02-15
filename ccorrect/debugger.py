import gdb
import sys
from ccorrect.parser import FuncCallParser
from dataclasses import dataclass


@dataclass
class FuncStats:
    name: str
    called: int
    args: list
    returns: list


class FuncFinishBreakpoint(gdb.FinishBreakpoint):
    def __init__(self, stats, func_location, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stats = stats
        self.func_location = func_location

    def stop(self):
        self.stats[self.func_location].returns.append(self.return_value)
        return False

    def out_of_scope(self):
        # TODO handle this
        print(f"TODO abnormal finish")


class FuncBreakpoint(gdb.Breakpoint):
    def __init__(self, stats, failures, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stats = stats
        self.failures = failures

    def get_args(self):
        try:
            frame = gdb.newest_frame()  # TODO investigate newest_frame() vs selected_frame()
            block = frame.block()
            args = {symbol.name: symbol.value(frame) for symbol in block if symbol.is_argument}
            return args
        except RuntimeError:
            print("cannot get args")
            return None

    def stop(self):
        # TODO allow force fail (don't execute function and change its return value and/or errno)
        # TODO collect args as stats
        # TODO collect number of times it has been called as stats
        # TODO collect return value as stats

        # TODO also keep type of args and return value

        fail = self.location in self.failures
        if not fail:
            # TODO investigate more
            # if we can't set finish breakpoint, it's because the frame must be a dummy frame (meaning it's called by gdb so we don't want to keep stats of it)
            try:
                FuncFinishBreakpoint(self.stats, self.location)
            except ValueError:
                print(f"Cannot set finish breakpoint for '{self.location}'")
                return False

        args = self.get_args()
        # TODO this allows to get arguments by their index, BUT is there a guarantee that the order is respected?
        #       Maybe It is for the best to just access the arg with its key but the problem is that it changes depending on the debug symbols 
        # for i, (k, v) in enumerate(args.copy().items()):
        #     args[0] = v

        if self.location not in self.stats:
            self.stats[self.location] = FuncStats(self.location, 1, [args], [])
        else:
            self.stats[self.location].called += 1
            self.stats[self.location].args.append(args)

        stats = self.stats[self.location]

        if fail:  # TODO fail not every time but like ctester does: the 1, 4 and 5 times for example
            # https://sourceware.org/gdb/onlinedocs/gdb/Convenience-Vars.html
            # ici set une convenience variable contenant l'evaluation de self.failures[self.location].returns
            # ensuite, la sauver dans self.stats[self.location].returns
            # ensuite, call gdb.execute("return $convenience_variable")
            failure = self.failures[self.location]

            err_ret = gdb.parse_and_eval(failure["return"])
            gdb.set_convenience_variable("__Debugger_return_var", err_ret)
            stats.returns.append(gdb.convenience_variable('__Debugger_return_var'))
            gdb.execute(f"return $__Debugger_return_var")
            # TODO handle case where if errno might not be in current context
            if "errno" in failure and failure["errno"]:
                print(f"ERRNO SET TO {failure['errno']}")
                gdb.execute(f"errno = {failure['errno']}")

        return False


class Debugger():
    def __init__(self, source_files=None, watches=None, excludes=None, failures=None, timeout=0):
        self.stats = {}
        self.__failures = {}
        self.__watches = set()
        self.timeout = timeout

        if source_files:
            self.add_watches_from_sources(source_files)
        if watches:
            self.add_watches(watches)
        if excludes:
            self.add_excludes(excludes)
        if failures:
            self.__failures = failures

        gdb.events.stop.connect(self._stop_event_handler)
        gdb.events.exited.connect(self._exited_event_handler)

        # if debuginfod is present, enable it to get debug symbols from files without them --> useful for libc
        # TODO adapt this for the inginious container (it's better if we get debug symbols for the libc directly from the container for performance purposes)
        gdb.execute("set debuginfod enabled on")

    def add_watches_from_sources(self, source_files):
        for f in source_files:
            func_calls = FuncCallParser(f).parse()
            if func_calls:
                self.__watches.update(func_calls)

    def add_watches(self, functions):
        self.__watches.update(functions)

    def add_excludes(self, functions):
        self.__watches.difference_update(set(functions))

    def set_failures(self, failures):
        self.__failures = failures

    def start(self):
        gdb.execute("start")

        # create breakpoints after start command to avoid the address sanitizer setup
        for func in self.__watches:
            FuncBreakpoint(self.stats, self.__failures, func)

        if self.timeout:
            gdb.execute("handle SIGALRM stop")  # tell gdb to stop when the inferior receives a SIGALRM
            gdb.parse_and_eval(f"alarm({self.timeout})")

        return gdb

    def finish(self):
        # detach inferior preocess to allow the leak sanitizer to work
        # https://stackoverflow.com/a/54373833
        gdb.execute("detach")

    def call(self, funcname, args=None):
        parsed_args = []
        if args is not None:
            for i, arg in enumerate(args):
                # TODO if arg is not a gdb.Value, parse it using the type from the function respective arg
                var_name = f"tmp_arg{i}"
                gdb.set_convenience_variable(var_name, arg)
                parsed_args.append(f"${var_name}")

        return gdb.parse_and_eval(f"{funcname}({', '.join(parsed_args)})")

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
