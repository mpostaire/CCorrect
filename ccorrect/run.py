import subprocess
import shlex


def run(test_script, silent_gdb=True):
    cmd = f'gdb -batch{"-silent" if silent_gdb else ""} -ex "python __name__ = \'gdb\'" -x "{test_script}"'
    p = subprocess.run(shlex.split(cmd))
    if p.returncode != 0:
        return

    try:
        with open("results.txt", "r") as f:
            results = []
            for line in f.readlines():
                result = line.strip().split(":")
                results.append({"success": bool(result[0]), "problem": result[1], "description": result[2], "weight": int(result[3])})

            return results
    except FileNotFoundError:
        return []
