import logging

class ColorFormatter(logging.Formatter):

    message_format = "[{levelname:^8}] : {message}"

    FORMATS = {
        logging.DEBUG: f"\33[95m{message_format}\33[0m",
        logging.INFO: f"\33[36m{message_format}\33[0m",
        logging.WARNING: f"\33[33m{message_format}\33[0m",
        logging.ERROR: f"\33[31m{message_format}\33[0m",
        logging.CRITICAL: f"\33[1m\33[31m{message_format}\33[0m",
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, style="{")
        return formatter.format(record)

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(logging.BASIC_FORMAT))

logger = logging.getLogger("RampEditor")
logger.handlers = [handler]

logger.setLevel(logging.ERROR) 