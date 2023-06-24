# CCorrect

A python module to write, grade and provide feedback for exercices in C using gdb.

## Features

- [x] Programmable function failures (don't execute function: immediately return)
    - [x] change return value
    - [x] change return args (pointer args)
    - [x] set errno
- [x] Ban usage of some functions
- [ ] Segfault crash report
    - [x] Show backtrace with stack variables at the moment of the crash
    - [ ] Heap visualization at the moment of the crash?
- [x] Support execution timeout
- [x] Make an API that makes gdb's API easier and an API for writing tests
    - [x] gdb.Value builder from python objects
        - [x] build scalars, structs, arrays, enums, unions
        - [x] build stucts with flexible array
    - [x] call functions
    - [x] tests API
- [x] Threads support
    - [x] keep track of number of threads
    - [x] use libtsan's output
- [x] Memleak detection (libasan)
- [x] Inginious integration
- [x] CI
    - [x] unit tests value builder
    - [x] unit tests timeout
    - [x] unit tests function call, watch and fail
    - [x] unit tests for funccall parser
    - [x] unit tests catch errors (SIGSEGV, SIGFPE, double free)
    - [x] unit tests on different exercises (test on an expected results.yml)

<!-- 
check all if malloc, SIGALRM setter etc in CCorrect internals dont fail, raise exception if they do

-> IMPORTANT: test segfaults, double free, floating point exception, etc feedback WITH AND WITHOUT libasan
              test timeout feedback
            TEST crash_log feedback on inginious (only if asan_log not present but crash_log is...)

-> CHECK if ccorrect is compatible with multithreading and programs that fork


-> LIMITATION?: when the inferior forks itself -> what to to in this case?

-> LIMITATION?: gdb.Value builder: flexible arrays at the end of a struct

-> LIMITATION?: parser of source files to find function calls is limited to C99 with some C11 features (but not all) -> maybe fixable by using clang's python api instead of pycparser

-> LIMITATION?: MUST be compiled with '-fno-builtin' (it works without this but can miss some functions: printf can be converted into puts by the compiler. Doing this prevents it)
    -> understand this better as it's not completely accurate
gcc sample.c other.c -g -fno-builtin -o sample


-> WARNING: there MUST be debug symbols available for libc, libasan, libtsan or more (depending on the tested program)


Compare why using libasan is better than valgrind:
valgrind integration (using valgrind's gdb server) to collect stats on memleaks, threads, open file descriptors, other memory stats
      -> https://valgrind.org/docs/manual/manual-core-adv.html
      -> https://indico.cern.ch/event/392796/contributions/1827927/attachments/1196707/1744649/vgdb.pdf
 -> if we monitor a function and compare start breakpoint and finish breakpoint mem leaks with (monitor leak_check) command, we can deduce if there was a memory leak
      inside this function (example application: student needs to code a function that manipulates a linked list, like removing elements, we can check
      that they have correctly freed the memory)
  -> OR maybe simpler: do it at the end and parse the complete oupput trace to check if our monitored function is in it
  -> Be careful of eventual libraries that may cause leakage that is not caused by the student -> find a way to detect this to not report this leak
-->
