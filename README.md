# CCorrect

A python module to write, grade and provide feedback for exercices in C using gdb.

## TODO

- [ ] Programmable function failures/change return value and args
    - [x] programmable function failures
    - [x] change return value
    - [ ] change return args (pointer args)
- [ ] Segfault crash report
    - [ ] Stack/heap visualization on crash
    - [ ] Show lines with values next to variables names
- [x] Support execution timeout
- [x] Make an API that makes gdb's API easier and an API for writing tests
    - [x] gdb.Value builder from python objects
    - [x] call functions
    - [x] tests API
- [ ] Threads support
- [x] Memleak detection (libasan)
- [x] Inginious integration
- [ ] CI
    - [x] unit tests value builder
    - [x] unit tests timeout
    - [x] unit tests function call, watch and fail
    - [ ] unit tests catch errors (SIGSEGV, SIGFPE, ...)
    - [ ] unit tests on different exercises (test on an expected results.yml)

<!-- 
## TODO

check all if malloc, SIGALRM setter etc in CCorrect internals dont fail, raise exception if they do

-> IMPORTANT: test segfaults, double free, floating point exception, etc feedback WITH AND WITHOUT libasan
              test timeout feedback
-> ADD exception handling everywhere if there is an error inside ccorrect (there are exception raised but the program continues execution???)

-> edit return values in parameters (force fail, etc) NOT IMPORTANT RIGHT NOW

https://gcc.gnu.org/onlinedocs/gcc/Instrumentation-Options.html
maybe these gcc flags wont work cause we call functions using gdb: if this is the case use own implementation
-fsanitize=undefined

-> LIMITATION: when the inferior forks itself -> what to to in this case?

# TODO investigate this message when timeout while debugging
# gdb.error: The program being debugged was signaled while in a function called from GDB.
# GDB remains in the frame where the signal was received.
# To change this behavior use "set unwindonsignal on".

TODO Once I have something usable, get feedback/ask for other feature requests and test robustness in a real case


TODO using clang's python lib for ast traversal may be better as it won't need the fake libc headers
        BUT maybe will cause problems with compilation using gcc (as gcc doesn't support the same extensions that clang)


TODO test on functions like _mm256_set_ps (this works but we dont get its return value) ALSO very strange: using gdb manually I can't manage to set a breakpoint on it
      -> works but there should be a warning in the documentation of CTester saying that it will also go through all includes and check
          function calls from there recursively

TODO track new thread creation/deletion and collect stats on them (number, the amount of time they ran, ...)

TODO valgrind integration (using valgrind's gdb server) to collect stats on memleaks, threads, open file descriptors, other memory stats
      -> https://valgrind.org/docs/manual/manual-core-adv.html
      -> https://indico.cern.ch/event/392796/contributions/1827927/attachments/1196707/1744649/vgdb.pdf
 -> if we monitor a function and compare start breakpoint and finish breakpoint mem leaks with (monitor leak_check) command, we can deduce if there was a memory leak
      inside this function (example application: student needs to code a function that manipulates a linked list, like removing elements, we can check
      that they have correctly freed the memory)
  -> OR maybe simpler: do it at the end and parse the complete oupput trace to check if our monitored function is in it
  -> Be careful of eventual libraries that may cause leakage that is not caused by the student -> find a way to detect this to not report this leak

TODO add to limitations that the parser of source files to find function calls is limited to C99 with some C11 features (but not all)

TODO C error at line x -> transform x (line student code + template wrapping C code) into y (line student code)
   -> USE '#line x "filename"' preprocessor directive to set current line to 'x' (and change file name to filename) (that'll offset the following lines)
          put #line 0 (or 1 as 0 may not be possible in all compilers???) just before the template

TODO MUST be compiled with '-fno-builtin' (it works without this but can miss some functions: printf can be converted into puts by the compiler. Doing this prevents it)
    -> understand this better as it's not completely accurate
gcc sample.c other.c -g -fno-builtin -o sample

TODO handle signals (like SIGSEGV, SIGALRM, ...) https://stackoverflow.com/a/25423589

-->
