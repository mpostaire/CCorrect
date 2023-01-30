# CCorrect
<!-- 
## TODO

- Programmable function failures/change return value and args
    - (ordered set of increasing integers where a number x in this set is the number of call that should fail)
    - change return value (done)
    - change return args (pointer args)
- Segfault crash report
    - Stack/heap visualization on crash
    - Show lines with values next to variables names
- Support execution timeout
- Feature-parity with CTester (every feature of CTester must be implemented)
    - small C lib to implement non gdb stuff like the trap buffer mechanism of CTester
- Make an API that fully hides gdb for easy tests writing
- Threads support (not enabled by default)
- Memleak detection (not enabled by default)
- Inginious integration
- gettext support
- Continuous integration
    - test on different exercises
    - test function call parser on "ugly" code
- Once I have something usable, get feedback/ask for other feature requests and test robustness in a real case

## TODO before S3: robustness test

- simple stack semaine 4 du P3 -> copier exo en utilisant le nouveau ctester (masquer ancien exo) -> je suis admin sur le inginious du P3
    - for this I don't need to implement threads/memleaks/gettext


TODO using clang's python lib for ast traversal may be better as it won't need the fake libc headers
        BUT maybe will cause problems with compilation using gcc (as gcc doesn't support the same extensions that clang) -->
