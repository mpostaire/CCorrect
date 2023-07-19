// The following includes are needed by CCorrect
#include <stdlib.h>
#include <unistd.h>

#include <stdio.h>
#include <fcntl.h>
#include <errno.h>
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

typedef struct struct_flexible_array {
    int size;
    int array[];
} struct_flexible_array;

typedef struct struct_nested_flexible_array {
    char value;
    struct struct_flexible_array nested;
} struct_nested_flexible_array;

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

typedef union {
    char c;
    test_struct t;
    long l;
} test_union;

int test_struct_mean(test_struct array[], size_t len) {
    int total = 0;
    for (int i = 0; i < len; i++)
        total += array[i].i;
    return total / len;
}

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

void wrap_free(void *ptr) {
    free(ptr);
}

void return_arg(test_struct **ts, int i) {
    *ts = malloc(sizeof(test_struct));
    (*ts)->c = i / 2;
    (*ts)->i = i * 2;
}

int test_return_arg(int i) {
    test_struct *ts;
    return_arg(&ts, i);
    return ts->c * ts->i;
}

int open_file_r(char *path) {
    return open(path, O_RDONLY);
}

int test_flexible(struct_flexible_array *a) {
    int sum = 0;
    for (int i = 0; i < a->size; i++)
        sum += a->array[i];
    return sum;
}

int main() {
    node a = {0};
    node_ext b = {0};
    struct_nested_flexible_array c = {0};
    node_array d = {0};
    node_array2d e = {0};
    node_array3d f = {0};
    test_struct g = {0};
    test_struct_packed h = {0};
    str_struct i = {0};
    enum enumeration k = enum_elem1;
    test_union l = {0};

    return 0;
}
