// The following includes are needed by CCorrect
#include <stdlib.h>
#include <unistd.h>

#include <string.h>

typedef struct {
    char c;
    int i;
} test_struct;

typedef struct {
    char c;
    int i;
} __attribute__((packed)) test_struct_packed;

typedef struct node {
    int value;
    struct node *next;
} node;

typedef struct {
    int value;
    node next;
} node_ext;

// typedef struct node_flexible_array {
//     int value;
//     int next[];
// } node_flexible_array;

typedef struct {
    int value;
    int next[4];
} node_array;

typedef struct {
    int value;
    int next[4][2];
} node_array2d;

typedef struct {
    int value;
    int next[4][2][3];
} node_array3d;

typedef struct {
    int value;
    char *name;
} str_struct;

enum enumeration {
    enum_elem1,
    enum_elem2,
    enum_elem3,
};

size_t str_struct_name_len(str_struct *s) {
    return strlen(s->name);
}

char *repeat_char(char c, int count) {
    char *str = malloc(count + 1);
    if (!str)
        return NULL;

    str[count] = '\0';
    while (count--)
        str[count] = c;

    return str;
}

void loop(void) {
    while (1);
}

void test_free(void) {
    char *tmp = malloc(8);
    free(tmp);
}

int main() {
    node a = {0};
    node_ext b = {0};
    // node_flexible_array c = {0};
    node_array d = {0};
    node_array2d e = {0};
    node_array3d f = {0};
    test_struct g = {0};
    test_struct_packed h = {0};
    str_struct i = {0};
    enum enumeration k = enum_elem1;

    return 0;
}
