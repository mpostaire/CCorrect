import subprocess
import shlex
import os
from yaml import safe_load as yaml_load


def run(test_script, silent_gdb=True):
    """Starts the GDB process that executes `test_script`, returns a dictionnary containing the results of the tests or None if there are none."""
    cmd = _get_cmd(test_script, silent_gdb)
    p = subprocess.run(shlex.split(cmd))
    if p.returncode != 0:
        raise RuntimeError(f"GDB exited with return code: {p.returncode}")

    try:
        with open(os.path.join(os.path.dirname(test_script), "results.yml"), "r") as f:
            return yaml_load(f)
    except FileNotFoundError:
        return None


def _get_cmd(test_script, silent_gdb=True):
    """Returns the command that is used by `run` to start the GDB process."""
    return f'gdb -batch{"-silent" if silent_gdb else ""} -ex "python __name__ = \\"gdb\\"" -x "{test_script}"'
