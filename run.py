# run.py
import sys
import asyncio
from monitor import run_monitoring

# Reconfigure console output to UTF-8 to prevent Windows terminal encoding errors
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

if __name__ == "__main__":
    try:
        asyncio.run(run_monitoring())
    except KeyboardInterrupt:
        print("\nMonitoring system stopped by user.")
