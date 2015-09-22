import os, threading, logging

from logging import handlers

import lazylibrarian
from lazylibrarian import formatter

MAX_SIZE = 51200 # 5 Bytes
MAX_FILES = 5


# Simple rotating log handler that uses RotatingFileHandler
class RotatingLogger(object):

    def __init__(self, filename, max_size=MAX_SIZE, max_files=MAX_FILES):

        self.filename = filename
        self.max_size = max_size
        self.max_files = max_files

    def initLogger(self, loglevel=1):

        l = logging.getLogger('lazylibrarian')
        l.setLevel(logging.DEBUG)
        

        self.filename = os.path.join(lazylibrarian.LOGDIR, self.filename)

        filehandler = handlers.RotatingFileHandler(self.filename, maxBytes=self.max_size, backupCount=self.max_files)
        filehandler.setLevel(logging.DEBUG)
        

        fileformatter = logging.Formatter('%(asctime)s - %(levelname)-7s :: %(message)s', '%d-%b-%Y %H:%M:%S')

        filehandler.setFormatter(fileformatter)
        l.addHandler(filehandler)


        if loglevel:
            consolehandler = logging.StreamHandler()
            if loglevel == 1:
                consolehandler.setLevel(logging.INFO)
            if loglevel == 2:
                consolehandler.setLevel(logging.DEBUG)
            consoleformatter = logging.Formatter('%(asctime)s - %(levelname)s :: %(message)s', '%d-%b-%Y %H:%M:%S')
            consolehandler.setFormatter(consoleformatter)
            l.addHandler(consolehandler)

    def log(self, message, level):

        logger = logging.getLogger('lazylibrarian')

        threadname = threading.currentThread().getName()

        if level != 'DEBUG':
            lazylibrarian.LOGLIST.insert(0, (formatter.now(), message, level, threadname))

        message = threadname + ' : ' + message

        if level == 'DEBUG':
            logger.debug(message)
        elif level == 'INFO':
            logger.info(message)
        elif level == 'WARNING':
            logger.warn(message)
        else:
            logger.error(message)

lazylibrarian_log = RotatingLogger('lazylibrarian.log', lazylibrarian.LOGSIZE, lazylibrarian.LOGCOUNT)

def debug(message):
    lazylibrarian_log.log(message, level='DEBUG')

def info(message):
    lazylibrarian_log.log(message, level='INFO')

def warn(message):
    lazylibrarian_log.log(message, level='WARNING')

def error(message):
    lazylibrarian_log.log(message, level='ERROR')
