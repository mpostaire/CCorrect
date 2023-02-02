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
        BUT maybe will cause problems with compilation using gcc (as gcc doesn't support the same extensions that clang)





how to use gdb.Value:
https://sourceware.org/gdb/onlinedocs/gdb/Values-From-Inferior.html

TODO also pass python variable student_code containing the code as a string of the student only (so we can monitor all func calls of the student and not the additionals added by the template)

TODO test on functions like _mm256_set_ps (this works but we dont get its return value) ALSO very strange: using gdb manually I can't manage to set a breakpoint on it
      --> works but there should be a warning in the documentation of CTester saying that it will also go through all includes and check
          function calls from there recursively

TODO track new thread creation/deletion and collect stats on them (number, the amount of time they ran, ...)

TODO valgrind integration (using valgrind's gdb server) to collect stats on memleaks, threads, open file descriptors, other memory stats
      ---> https://valgrind.org/docs/manual/manual-core-adv.html
      ---> https://indico.cern.ch/event/392796/contributions/1827927/attachments/1196707/1744649/vgdb.pdf
 ---> if we monitor a function and compare start breakpoint and finish breakpoint mem leaks with (monitor leak_check) command, we can deduce if there was a memory leak
      inside this function (example application: student needs to code a function that manipulates a linked list, like removing elements, we can check
      that they have correctly freed the memory)
  ----> OR maybe simpler: do it at the end and parse the complete oupput trace to check if our monitored function is in it
  ----> Be careful of eventual libraries that may cause leakage that is not caused by the student --> find a way to detect this to not report this leak

TODO add to limitations that the parser of source files to find function calls is limited to C99 with some C11 features (but not all)

TODO add function ban list: functions the student can't use (use parser but may pose problems... because of the limitiations of the parser)
      ----> ALSO put breakpoint on them in case they escaped the parser detection so that we can detect them at runtime

TODO C error at line x --> transform x (line student code + template wrapping C code) into y (line student code)
   ---> USE '#line x "filename"' preprocessor directive to set current line to 'x' (and change file name to filename) (that'll offset the following lines)
          put #line 0 (or 1 as 0 may not be possible in all compilers???) just before the template

TODO capture student's program stdout/stderr and put it in a variable in returned stats

TODO MUST be compiled with '-fno-builtin' (it works without this but can miss some functions: printf can be converted into puts by the compiler. Doing this prevents it)
    ---> understand this better as it's not completely accurate
gcc sample.c other.c -g -mavx2 -fno-builtin -o sample


TODO Maybe unit test should be kept in C with Cunit (investigate if doing it in python with gdb has a weir syntax or something...)
      ---> keeping Cunit allows for better coherence for keeping trap_buffer() in C (seems impossible in python??)
      ---> BUT we need a way for SANDBOX_BEGIN and SANDBOX_END to reset the python collected stats (and other things too???)
          To do this, make breakpoint on SANDBOX_END (compile this func with volatile keyword to prevent it being optimized away??)
          AND each time this special breakpoint is called, reset python collected stats (and other things too???)
  -----> BUT doing this the stats are not possible to get from the unit tests so kinda useless...


TODO handle signals (like SIGSEGV, SIGALRM, ...) https://stackoverflow.com/a/25423589

TODO gdb print and call and convenience variables are very limited ---> I think it's impossible to unit test inside python gdb
      -----> ATTENTION: Maybe it can still work (maybe only accessing return and argument values of the student code function is ok)
                          Check already existing ctester tests to see if they only test this AND write some quick tests in python to see if it works

     ---> still use it to collect stats ONLY between SANDBOX_BEGIN and SANDBOX_END
  -----> keep trace of ecerything that happens and needs to be remembered, then analyse it.
      ----> the gdb python script will be defined tests: should watch this varialbe, and student code return should be equal to something...
              then compare this with the python gdb trace... I'm not sure that's good...
              ----> MAYBE using my original idea with the AST editing is the solution... (but there won't be accurate student feedback on segfaults etc
                      as this changes the student code ---> write a translator program that changes the error message accordignly???)


TODO check compilation with -fsanitize=address
Enable AddressSanitizer, a fast memory error detector. Memory access instructions are instrumented to detect out-of-bounds and use-after-free bugs.
The option enables -fsanitize-address-use-after-scope. See https://github.com/google/sanitizers/wiki/AddressSanitizer for more details.
The run-time behavior can be influenced using the ASAN_OPTIONS environment variable. When set to help=1, the available options are shown at 
startup of the instrumented program. See https://github.com/google/sanitizers/wiki/AddressSanitizerFlags#run-time-flags for a list of supported options.
The option cannot be combined with -fsanitize=thread or -fsanitize=hwaddress. Note that the only target -fsanitize=hwaddress is currently supported on is AArch64.

TODO if I intercept all alloc functions, I can get from their argument the allocated size, and by using the type of the variable its put into, I can do
      like pythontutor to show arrays... This may not be that simple (especially the target type deduction)


-->
