#!/bin/bash

if [ $# -lt 2 ]; then
    echo "Usage: ${0} test_script tested_program [source1.c source2.c ...]"
    exit 1
elif [ $# -ge 3 ]; then
    printf -v args '"%s",' "${@:3}"
fi

# export PYTHONPATH="$PWD:$PYTHONPATH"
export PYTHONPATH="$PWD/..:$PYTHONPATH"
# gdb -batch -ex "python source_files = [${args%,}]; __name__ = 'gdb'" -x "${1}" "${2}"
gdb -batch -ex "python source_files = [${args%,}];" -x "${1}" "${2}"
# gdb -batch-silent -ex "python source_files = [${args%,}]" -x "${1}" "${2}"
