"""Start both Lena and Susi bots in parallel."""

import subprocess
import sys
import time

def main():
    procs = [
        subprocess.Popen(
            [sys.executable, "lena/main.py"],
            stdout=sys.stdout, stderr=sys.stderr,
        ),
        subprocess.Popen(
            [sys.executable, "susi/main.py"],
            stdout=sys.stdout, stderr=sys.stderr,
        ),
    ]
    print("Both bots started", flush=True)

    while True:
        for i, p in enumerate(procs):
            ret = p.poll()
            if ret is not None:
                name = "Lena" if i == 0 else "Susi"
                print(f"{name} crashed with code {ret}, restarting...", flush=True)
                cmd = procs[i].args
                procs[i] = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
        time.sleep(5)

if __name__ == "__main__":
    main()
