#!/bin/bash

if [ $# -lt 2 ]; then
    echo "Usage: ${0} test_script tested_program"
    exit 1
fi

export PYTHONPATH="$PWD/..:$PYTHONPATH"
gdb -batch-silent -x "${1}" "${2}"
