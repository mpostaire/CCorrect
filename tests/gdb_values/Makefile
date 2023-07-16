CC=gcc
CFLAGS=-Wall -Wextra -O0 -ggdb3 -fno-builtin -fsanitize=address -std=c99

main: main.c
	$(CC) $^ $(CFLAGS) -o $@

clean:
	rm -rf main
