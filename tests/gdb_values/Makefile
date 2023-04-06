CC=gcc
CFLAGS=-Wall -Wextra -O0 -g3 -fno-builtin -fsanitize=address -std=c99

main: main.c
	$(CC) $^ $(CFLAGS) -o $@

clean:
	rm -rf main
