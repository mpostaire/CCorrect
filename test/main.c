// The following includes are needed by CCorrect
#include <stdlib.h>
#include <unistd.h>

// TODO handle this case
// typedef struct node_packed {
//     int value;
//     struct node_packed *next;
// } __attribute__((packed)) node_packed;

typedef struct node {
    int value;
    struct node *next;
} node;

typedef struct node_ext {
    int value;
    struct node next;
} node_ext;

// typedef struct node_flexible_array {
//     int value;
//     int next[];
// } node_flexible_array;

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

int main() {
    node a = {0};
    node_ext b = {0};
    // node_flexible_array c = {0};
    node_array d = {0};
    node_array2d e = {0};
    node_array3d f = {0};

    return 0;
}
