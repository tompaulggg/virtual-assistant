"""Start both Lena and Susi bots in parallel."""

import asyncio
import subprocess
import sys

def main():
    procs = [
        subprocess.Popen([sys.executable, "lena/main.py"]),
        subprocess.Popen([sys.executable, "susi/main.py"]),
    ]
    print("Both bots started")
    for p in procs:
        p.wait()

if __name__ == "__main__":
    main()
