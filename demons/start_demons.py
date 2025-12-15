import subprocess
import os
import sys

BASE_DIR = r"C:\xampp\htdocs\stock_pg"
os.chdir(BASE_DIR)
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

DEMONS = [
    #("datafeed_aggregator", "demons/datafeed_aggregator.py"),
    ("strategy_runner",     "demons/strategy_runner.py"),
    ("execution_engine",    "demons/execution_engine.py"),
    ("fake_broker",         "demons/fake_broker.py"),
    #("health_monitor",      "demons/health_monitor.py"),  # можно закомментировать
]

def main():
    os.chdir(BASE_DIR)
    processes = []
    for name, path in DEMONS:
        print(f"Starting {name}...")
        p = subprocess.Popen([sys.executable, path])
        processes.append((name, p))

    print("All demons started.")
    for name, p in processes:
        print(f"{name} PID={p.pid}")

if __name__ == "__main__":
    main()
