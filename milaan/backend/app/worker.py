import argparse, threading
from .config import Settings
from .database import Database
from .jobs import worker_loop, run_once, cleanup

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Process one queued job and exit")
    parser.add_argument("--cleanup", action="store_true", help="Purge expired records and exit")
    args = parser.parse_args()
    settings = Settings()
    database = Database(settings.database_url, pool_size=settings.database_pool_size, max_overflow=settings.database_max_overflow)
    if args.cleanup: cleanup(database, settings)
    elif args.once: print("Processed one job" if run_once(database, settings) else "No queued jobs")
    else:
        stop = threading.Event()
        try: worker_loop(database, settings, stop)
        except KeyboardInterrupt: stop.set()
