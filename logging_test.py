#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2014 OpenERP SA (<http://www.openerp.com>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import logging
import logging.handlers
import os
# import platform
import pprint
# import release
import sys
import threading

_logger = logging.getLogger(__name__)

def log(logger, level, prefix, msg, depth=None):
    indent=''
    indent_after=' '*len(prefix)
    for line in (prefix + pprint.pformat(msg, depth=depth)).split('\n'):
        logger.log(level, indent+line)
        indent=indent_after

path_prefix = os.path.realpath(os.path.dirname(os.path.dirname(__file__)))

class PostgreSQLHandler(logging.Handler):
    """ PostgreSQL Loggin Handler will store logs in the database, by default
    the current database, can be set using --log-db=DBNAME
    """
    def emit(self, record):
        ct = threading.current_thread()
        ct_db = getattr(ct, 'dbname', None)
        dbname = tools.config['log_db'] if tools.config['log_db'] and tools.config['log_db'] != '%d' else ct_db
        if not dbname:
            return
        with tools.ignore(Exception), tools.mute_logger('openerp.sql_db'), sql_db.db_connect(dbname, allow_uri=True).cursor() as cr:
            cr.autocommit(True)
            msg = tools.ustr(record.msg)
            if record.args:
                msg = msg % record.args
            traceback = getattr(record, 'exc_text', '')
            if traceback:
                msg = "%s\n%s" % (msg, traceback)
            # we do not use record.levelname because it may have been changed by ColoredFormatter.
            levelname = logging.getLevelName(record.levelno)

            val = ('server', ct_db, record.name, levelname, msg, record.pathname[len(path_prefix)+1:], record.lineno, record.funcName)
            cr.execute("""
                INSERT INTO ir_logging(create_date, type, dbname, name, level, message, path, line, func)
                VALUES (NOW() at time zone 'UTC', %s, %s, %s, %s, %s, %s, %s, %s)
            """, val)

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, _NOTHING, DEFAULT = range(10)
#The background is set with 40 plus the number of the color, and the foreground with 30
#These are the sequences need to get colored ouput
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"
COLOR_PATTERN = "%s%s%%s%s" % (COLOR_SEQ, COLOR_SEQ, RESET_SEQ)
LEVEL_COLOR_MAPPING = {
    logging.DEBUG: (BLUE, DEFAULT),
    logging.INFO: (GREEN, DEFAULT),
    logging.WARNING: (YELLOW, DEFAULT),
    logging.ERROR: (RED, DEFAULT),
    logging.CRITICAL: (WHITE, RED),
}

class DBFormatter(logging.Formatter):
    def format(self, record):
        record.pid = os.getpid()
        record.dbname = getattr(threading.currentThread(), 'dbname', '?')
        return logging.Formatter.format(self, record)

class ColoredFormatter(DBFormatter):
    def format(self, record):
        fg_color, bg_color = LEVEL_COLOR_MAPPING.get(record.levelno, (GREEN, DEFAULT))
        record.levelname = COLOR_PATTERN % (30 + fg_color, 40 + bg_color, record.levelname)
        return DBFormatter.format(self, record)

_logger_init = False
def init_logger(syslog=None, logfile=None):
    global _logger_init
    if _logger_init:
        return
    _logger_init = True

    logging.addLevelName(25, "INFO")

    # from tools.translate import resetlocale
    # resetlocale()

    # create a format for log messages and dates
    format = '%(asctime)s %(pid)s %(levelname)s %(dbname)s %(name)s: %(message)s'

    if False:
        pass
    # if syslog:
    #     # SysLog Handler
    #     if os.name == 'nt':
    #         handler = logging.handlers.NTEventLogHandler("%s %s" % (release.description, release.version))
    #     elif platform.system() == 'Darwin':
    #         handler = logging.handlers.SysLogHandler('/var/run/log')
    #     else:
    #         handler = logging.handlers.SysLogHandler('/dev/log')
    #     format = '%s %s' % (release.description, release.version) \
    #             + ':%(dbname)s:%(levelname)s:%(name)s:%(message)s'

    # elif logfile:
    #     # LogFile Handler
    #     logf = logfile
    #     try:
    #         # We check we have the right location for the log files
    #         dirname = os.path.dirname(logf)
    #         if dirname and not os.path.isdir(dirname):
    #             os.makedirs(dirname)
    #         if tools.config['logrotate'] is not False:
    #             handler = logging.handlers.TimedRotatingFileHandler(filename=logf, when='D', interval=1, backupCount=30)
    #         elif os.name == 'posix':
    #             handler = logging.handlers.WatchedFileHandler(logf)
    #         else:
    #             handler = logging.FileHandler(logf)
    #     except Exception:
    #         sys.stderr.write("ERROR: couldn't create the logfile directory. Logging to the standard output.\n")
    #         handler = logging.StreamHandler(sys.stdout)

    else:
        # Normal Handler on standard output
        handler = logging.StreamHandler(sys.stdout)

    # Check that handler.stream has a fileno() method: when running OpenERP
    # behind Apache with mod_wsgi, handler.stream will have type mod_wsgi.Log,
    # which has no fileno() method. (mod_wsgi.Log is what is being bound to
    # sys.stderr when the logging.StreamHandler is being constructed above.)
    def is_a_tty(stream):
        return hasattr(stream, 'fileno') and os.isatty(stream.fileno())

    if os.name == 'posix' and isinstance(handler, logging.StreamHandler) and is_a_tty(handler.stream):
        formatter = ColoredFormatter(format)
    else:
        formatter = DBFormatter(format)
    handler.setFormatter(formatter)

    logging.getLogger().addHandler(handler)

    # if tools.config['log_db']:
    #     db_levels = {
    #         'debug': logging.DEBUG,
    #         'info': logging.INFO,
    #         'warning': logging.WARNING,
    #         'error': logging.ERROR,
    #         'critical': logging.CRITICAL,
    #     }
    #     postgresqlHandler = PostgreSQLHandler()
    #     postgresqlHandler.setLevel(int(db_levels.get(tools.config['log_db_level'], tools.config['log_db_level'])))
    #     logging.getLogger().addHandler(postgresqlHandler)

    # Configure loggers levels
    # log_level='debug_rpc_answer'
    log_level='info'
    pseudo_config = PSEUDOCONFIG_MAPPER.get(log_level, [])

    # logconfig = ''  # tools.config['log_handler']

    logging_configurations = DEFAULT_LOG_CONFIGURATION + pseudo_config # + logconfig
    for logconfig_item in logging_configurations:
        loggername, level = logconfig_item.split(':')
        level = getattr(logging, level, logging.INFO)
        logger = logging.getLogger(loggername)
        logger.setLevel(level)

    for logconfig_item in logging_configurations:
        _logger.debug('logger level set: "%s"', logconfig_item)

DEFAULT_LOG_CONFIGURATION = [
    'openerp.workflow.workitem:WARNING',
    'openerp.http.rpc.request:INFO',
    'openerp.http.rpc.response:INFO',
    'openerp.addons.web.http:INFO',
    'openerp.sql_db:INFO',
    ':INFO',
]
PSEUDOCONFIG_MAPPER = {
    'debug_rpc_answer': ['openerp:DEBUG','openerp.http.rpc.request:DEBUG', 'openerp.http.rpc.response:DEBUG'],
    'debug_rpc': ['openerp:DEBUG','openerp.http.rpc.request:DEBUG'],
    'debug': ['openerp:DEBUG'],
    'debug_sql': ['openerp.sql_db:DEBUG'],
    'info': [],
    'warn': ['openerp:WARNING', 'werkzeug:WARNING'],
    'error': ['openerp:ERROR', 'werkzeug:ERROR'],
    'critical': ['openerp:CRITICAL', 'werkzeug:CRITICAL'],
}

if __name__ == '__main__':
    init_logger()
    import logging
    _logger = logging.getLogger(__name__)
    _logger.info('hola mundo 1')
    _logger.warn('hola mundo 2')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

'''
#!/usr/bin/env python

import argparse
import os
import subprocess
import logging


BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

# The background is set with 40 plus the number of the color, and the
# foreground with 30

# These are the sequences need to get colored ouput
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"


def formatter_message(message, use_color=True):
    if use_color:
        message = message.replace("$RESET", RESET_SEQ).replace(
            "$BOLD", BOLD_SEQ)
    else:
        message = message.replace("$RESET", "").replace("$BOLD", "")
    return message

COLORS = {
    'WARNING': YELLOW,
    'INFO': GREEN,
    'DEBUG': BLUE,
    'CRITICAL': YELLOW,
    'ERROR': RED
}


class ColoredFormatter(logging.Formatter):
    def __init__(self, msg, use_color=True):
        logging.Formatter.__init__(self, msg)
        self.use_color = use_color

    def format(self, record):
        levelname = record.levelname
        if self.use_color and levelname in COLORS:
            levelname_color = COLOR_SEQ % (
                30 + COLORS[levelname]) + levelname + RESET_SEQ
            record.levelname = levelname_color
        return logging.Formatter.format(self, record)


# Custom logger class with multiple destinations
class ColoredLogger(logging.Logger):

    FORMAT = "[$BOLD%(name)s$RESET][%(levelname)s] %(message)s"
    COLOR_FORMAT = formatter_message(FORMAT, True)

    def __init__(self, name):
        logging.Logger.__init__(self, name, logging.DEBUG)

        color_formatter = ColoredFormatter(self.COLOR_FORMAT)

        console = logging.StreamHandler()
        console.setFormatter(color_formatter)

        self.addHandler(console)
        return


class LoggerTest(object):

    def __init__(self):
        self.prepare_logger()

    def prepare_logger(self):
        """
        Create the logger for the script
        @return True
        """
        logging.setLoggerClass(ColoredLogger)
        self.logger = logging.getLogger('odoo_lint')
        self.logger.setLevel(logging.DEBUG)
        return True

obj = LoggerTest()
obj.logger.info('Hello world!')
'''
