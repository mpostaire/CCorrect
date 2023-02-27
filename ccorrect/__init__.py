# allow access to debugger API depending if ccorrect is imported from inside gdb
try:
    from ccorrect.debugger import Debugger
    from ccorrect.values import gdb_array_iterator, gdb_struct_iterator, Ptr
except:
    from ccorrect.run import run
