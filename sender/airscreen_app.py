"""Entry point for the packaged AirScreen.exe (double-click app)."""
import multiprocessing
import sys

from airscreen_sender.app import run

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(run())
