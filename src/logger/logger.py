import logging
import os
from enum import Enum
from logging.handlers import RotatingFileHandler
from datetime import datetime

class LogLevel(Enum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

class LoggerConfig:

    def __init__(self, name=__name__, base_dir='../../logs', log_level=LogLevel.DEBUG):

        self.logger = logging.getLogger(name)
        self.logger.setLevel(LogLevel.DEBUG.value)
        self.base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), base_dir)
        self.log_level = log_level.value
        self._ensure_log_directory()
        self._setup_handlers()

    def _ensure_log_directory(self):
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def _setup_handlers(self):
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        debug_filename = os.path.join(self.base_dir, f"{datetime.now().strftime('%Y-%m-%d')}_debug.log")
        file_handler = RotatingFileHandler(
            debug_filename,
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding='utf-8'
        )
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(formatter)
        
        error_filename = os.path.join(self.base_dir, f"{datetime.now().strftime('%Y-%m-%d')}_error.log")
        error_file_handler = RotatingFileHandler(
            error_filename,
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding='utf-8'
        )
        error_file_handler.setLevel(LogLevel.ERROR.value)
        error_file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(LogLevel.INFO.value)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(error_file_handler)
        self.logger.addHandler(console_handler)

    def get_logger(self):
        return self.logger
