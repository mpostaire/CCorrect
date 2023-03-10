# allow access to debugger API depending if ccorrect is imported from inside gdb
try:
    from ccorrect._debugger import Debugger
    from ccorrect._values import Ptr, gdb_array_iterator, gdb_struct_iterator
except:
    from ccorrect._run import run
