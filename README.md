# CCorrect

A python module to write, grade and provide feedback for exercices in C using gdb.

## Documentation

Documentation for this project is currently only available by reading the docstrings in the source code.

A guide to porting an INGInious task using CTester to CCorrect is available [here](example/inginious_task_calloc2/README.md).

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
        - [ ] variadic functions
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
