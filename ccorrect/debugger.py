import gdb
from ccorrect.parser import FuncCallParser
from dataclasses import dataclass

# TODO https://stackoverflow.com/questions/42072355/debug-va-list-args-with-gdb

# TODO add some sort of thread debug support????


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
            print("cant get args")
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
    def __init__(self, source_files=None, watches=None, excludes=None, failures=None):
        self.stats = {}
        self.__failures = {}
        self.__watches = set()

        if source_files:
            self.add_watches_from_sources(source_files)
        if watches:
            self.add_watches(watches)
        if excludes:
            self.add_excludes(excludes)
        if failures:
            self.__failures = failures

        gdb.events.exited.connect(self._exit_handler)
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
        for func in self.__watches:
            FuncBreakpoint(self.stats, self.__failures, func)
        gdb.execute("start")
        return gdb

    def _exit_handler(self, event):
        print("event type: exit")
        if hasattr(event, 'exit_code'):
            print(f"exit code: {event.exit_code}")
        else:
            print("exit code not available")
