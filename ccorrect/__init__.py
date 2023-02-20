def test(program, source_files=None, watches=None, excludes=None, forbidden=None, timeout=0, silent_gdb=True):
    try:
        from ccorrect.debugger import Debugger
        return Debugger(program, source_files, watches, excludes, forbidden, timeout)
    except ImportError:
        import subprocess
        import shlex
        import inspect
        import sys

        test_script = inspect.stack()[1].filename

        cmd = f'gdb -batch{"-silent" if silent_gdb else ""} -x "{test_script}"'
        # TODO capture stdout, stderr??
        # TODO allow writing in stdin??
        p = subprocess.run(shlex.split(cmd))
        sys.exit(p.returncode)


def gdb_array_iterator(value):
    # type_of_elements = value.type.target()
    range_of_array = value.type.fields()[0].type.range()
    len_of_array = range_of_array[1] + 1
    for i in range(len_of_array):
        yield value[i]


def gdb_struct_iterator(value):
    for f in value.type.fields():
        yield f.name, value[f.name]


class Ptr(int):
    def __init__(self, value):
        if value < 0:
            raise ValueError(f"Ptr must be >= 0 (got {value})")

    def __str__(self):
        return hex(self)
