CC=gcc
CFLAGS=-Wall -Werror -O0 -ggdb3 -fno-builtin -fsanitize=address -std=c99
CPP=cppcheck
EXEC=test
CPPFLAGS=--error-exitcode=1
SRC=test.c student_code.c solutions/student_code_sol.c
OBJ=$(SRC:.c=.o)
SRC_COMP=test.c student_code_comp.c solutions/student_code_sol.c
OBJ_COMP=$(SRC_COMP:.c=.o)

all: $(EXEC)

$(EXEC): $(OBJ)
	$(CC) $^ $(CFLAGS) -o $@

%.o: %.c
	$(CC) -c $^ $(CFLAGS) -o $@

check: $(SRC_COMP)
	$(CPP) $(CPPFLAGS) $^

check_compile: $(OBJ_COMP)
	$(CC) $^ $(CFLAGS) -o $@

clean:
	rm -f $(EXEC) $(OBJ) check_compile $(OBJ_COMP)
