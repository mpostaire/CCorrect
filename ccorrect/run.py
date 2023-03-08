import subprocess
import shlex
from yaml import safe_load as yaml_load


def run(test_script, silent_gdb=True):
    cmd = f'gdb -batch{"-silent" if silent_gdb else ""} -ex "python __name__ = \'gdb\'" -x "{test_script}"'
    p = subprocess.run(shlex.split(cmd))
    if p.returncode != 0:
        return None

    try:
        with open("results.yml", "r") as f:
            return yaml_load(f)
    except FileNotFoundError:
        return None
