import logging
import time

from KFCAcademy.logging_formatters import NairobiGELFHandler
from KFCAcademy.settings import GRAYLOG_HOST, GRAYLOG_PORT

logger = logging.getLogger("heartbeat")
gelf_handler = NairobiGELFHandler(GRAYLOG_HOST, GRAYLOG_PORT,extra_fields=True)
logger.addHandler(gelf_handler)

while True:
    logger.info("KFCAcademy app is alive")
    time.sleep(60)