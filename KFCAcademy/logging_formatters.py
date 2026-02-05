import logging
from datetime import datetime
import pytz
from KFCAcademy import settings
import graypy
import json
import zlib
import struct

class NairobiGELFHandler(graypy.GELFUDPHandler):
    """
    Custom GELF handler that sets timestamp to Africa/Nairobi timezone
    """
    def emit(self, record):
        # Convert to Nairobi time BEFORE processing
        tz = pytz.timezone("Africa/Nairobi")
        utc_time = datetime.fromtimestamp(record.created, tz=pytz.utc)
        nairobi_time = utc_time.astimezone(tz)
        
        # Override the record's created time with Nairobi timestamp
        record.created = nairobi_time.timestamp()
        record.app = "KFC"
        record.env = "prod" if not settings.DEBUG else "dev"
        
        # Let parent handle the rest
        super().emit(record)