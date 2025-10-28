import logging
import sys
import os

def setup_logging():
    # Create logs directory if it doesn't exist
    log_dir = "/app/logs"
    os.makedirs(log_dir, exist_ok=True)

    # Configure logging with both console and file handlers
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(f"{log_dir}/auction-server-logs.log")
        ]
    )

def get_logger(name: str = __name__):
    return logging.getLogger(name)
