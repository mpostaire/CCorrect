CC=gcc
CFLAGS=-Wall -Wextra -g -fno-builtin -std=c99

main: main.o list.o
	$(CC) main.o list.o $(CFLAGS) -o $@

%.o: %.c
	$(CC) -c $^ $(CFLAGS) -o $@

clean:
	rm -rf main *.o
