// TODO check if a main is needed (can we just feed gdb object files and call function from there?

#include <stdio.h>
#include <stdlib.h>
#include "list.h"

int main() {
    node_ext b = {
        .next = { .next = NULL, .value = 4 },
        .value = 422
    };
    node_array c = {};
    node_variable_array *d = malloc(sizeof(node_variable_array) + 2 * sizeof(d->value));
    d->value = 32;
    d->next[0] = 1;

    node_variable_array *ptr = (node_variable_array *) malloc(sizeof(node_variable_array) + 2 * sizeof(int));
    ptr->value = 1;
    ptr->next[0] = 2;
    ptr->next[1] = 3;

    node_array2d d2 = {};
    node_array3d d3 = {};

    return 0;
}
