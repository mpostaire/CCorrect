#include <stdio.h>

struct point {
    int x;
    int y;
};

int a(int a, int b) {
    return a + b;
}

void b() {
    puts("Hello");
}

int c() {
    return 1;
}

int d(int a, int b) {
    return a * b;
}

char e(char c) {
    return c + 1;
}

int f(int a, int b, int c) {
    return a * b + c - e(b);
}

int main() {
    int result = a(3, 4);

    struct point p = {
        .x = 5,
        .y = f(6, 7, 1)
    };

    int arr[] = {1, 2, d(e(4), 5)};
    b();
    return c();
}
