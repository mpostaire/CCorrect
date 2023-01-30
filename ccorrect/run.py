#!/usr/bin/env python3

import os, subprocess, shlex

def run(program, source_files):
    cmd = f'gdb -batch -ex "python source_files = {source_files}; __name__ = \'gdb\'" -x "test.py" "{program}"'
    new_env = dict(os.environ, PYTHONPATH=f"{os.environ['PWD']}:{os.environ['PYTHONPATH'] if 'PYTHONPATH' in os.environ else ''}")
    # TODO capture stdout, stderr??
    # TODO allow writing in stdin??
    print(shlex.split(cmd))
    subprocess.run(shlex.split(cmd), env=new_env)
