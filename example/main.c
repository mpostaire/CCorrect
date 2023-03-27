// the following includes are important
#include <stdlib.h>
#include <unistd.h>

// include library to test
#include "list.h"

void memleak() {
    malloc(1);
}

void out_of_bounds() {
    int a[4] = {0};
    a[4] = 1;
}

int sigfpe() {
    return 1 / 0;
}

int sigsegv() {
    *(char *) NULL = 0;
}

int main() {
    return 0;
}
