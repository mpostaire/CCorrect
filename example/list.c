#include "list.h"
#include <stdlib.h>

size_t length(node *list) {
    size_t count = 0;
    for (node *n = list; n; n = n->next)
        count++;
    return count;
}

size_t count(node *list, int value) {
    size_t count = 0;
    for (node *n = list; n; n = n->next)
        if (n->value == value)
            count++;
    return count;
}

int push(node **list, int value) {
    node *n = malloc(sizeof(*n));
    if (!n) return -1;
    n->value = value;
    n->next = *list;
    *list = n;
    return 0;
}

int pop(node **list) {
    int val = (*list)->value;
    node *n = (*list)->next;
    free(*list);
    *list = n;
    return val;
}

void free_list(node *list) {
    node *next;
    for (node *n = list; n; n = next) {
        next = n->next;
        free(n);
    }
}
