#include <stddef.h>

// TODO handle this case
// typedef struct node {
//     int value;
//     struct node *next;
// } __attribute__((packed)) node;

typedef struct node {
    int value;
    struct node *next;
} node;

typedef struct node_ext {
    int value;
    struct node next;
} node_ext;

typedef struct node_variable_array {
    int value;
    int next[];
} node_variable_array;

typedef struct node_array {
    int value;
    int next[4];
} node_array;

typedef struct node_array2d {
    int value;
    int next[4][2];
} node_array2d;

typedef struct node_array3d {
    int value;
    int next[4][2][3];
} node_array3d;


void free_list(node *list);

size_t length(node *list);
size_t count(node *list, int value);

int push(node **list, int value);
int pop(node **list);
