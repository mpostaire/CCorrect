CC=gcc
# CFLAGS=-Wall -Wextra -O0 -g3 -fno-builtin -fsanitize=thread -std=c99
CFLAGS=-Wall -Wextra -O0 -g3 -fno-builtin -fsanitize=address -std=c99

main: main.o list.o
	$(CC) $^ $(CFLAGS) -o $@

%.o: %.c
	$(CC) -c $^ $(CFLAGS) -o $@

clean:
	rm -rf main *.o
