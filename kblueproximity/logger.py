"""Logging using Python logging handlers."""
from __future__ import annotations

import logging
import logging.handlers
import os
import stat
import threading
from itertools import count
from kblueproximity.paths import conf_dir

from kblueproximity.i18n import _

_LOGGER_COUNTER = count(1)


class Logger:
    def __init__(self):
        self._logger = logging.getLogger(f'kblueproximity.instance.{next(_LOGGER_COUNTER)}')
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        self._logger.handlers.clear()
        self._log_lock = threading.Lock()
        self._file_handler = None
        self._syslog_handler = None
        self.disable_syslogging()
        self.disable_filelogging()

    def _syslog_addresses(self):
        return [
            '/dev/log',
            '/run/systemd/journal/syslog',
        ]

    def _is_unix_socket(self, path: str) -> bool:
        try:
            mode = os.stat(path).st_mode
        except OSError:
            return False
        return stat.S_ISSOCK(mode)

    def _make_record(self, line):
        return self._logger.makeRecord(
            self._logger.name,
            logging.INFO,
            __file__,
            0,
            str(line),
            (),
            None,
        )

    def getFacilityFromString(self, facility):
        facility = str(facility or '').strip().strip("'\"")
        log_dict = {
            'local0': logging.handlers.SysLogHandler.LOG_LOCAL0,
            'local1': logging.handlers.SysLogHandler.LOG_LOCAL1,
            'local2': logging.handlers.SysLogHandler.LOG_LOCAL2,
            'local3': logging.handlers.SysLogHandler.LOG_LOCAL3,
            'local4': logging.handlers.SysLogHandler.LOG_LOCAL4,
            'local5': logging.handlers.SysLogHandler.LOG_LOCAL5,
            'local6': logging.handlers.SysLogHandler.LOG_LOCAL6,
            'local7': logging.handlers.SysLogHandler.LOG_LOCAL7,
            'user': logging.handlers.SysLogHandler.LOG_USER,
        }
        return log_dict.get(facility, logging.handlers.SysLogHandler.LOG_LOCAL7)

    def enable_syslogging(self, facility):
        if self._syslog_handler is not None:
            self.disable_syslogging()
        self.syslog_facility = self.getFacilityFromString(facility)
        for address in self._syslog_addresses():
            if (
                isinstance(address, str)
                and os.path.isabs(address)
                and (not os.path.exists(address) or not self._is_unix_socket(address))
            ):
                continue
            try:
                handler = logging.handlers.SysLogHandler(
                    address=address,
                    facility=self.syslog_facility,
                )
                handler.setFormatter(logging.Formatter('kblueproximity: %(message)s'))
                self._logger.addHandler(handler)
                self._syslog_handler = handler
                self.syslogging = True
                return
            except (OSError, ValueError, TypeError):
                continue
        self.disable_syslogging()

    def disable_syslogging(self):
        if self._syslog_handler is not None:
            try:
                self._logger.removeHandler(self._syslog_handler)
                self._syslog_handler.close()
            except Exception:
                pass
            self._syslog_handler = None
        self.syslogging = False
        self.syslog_facility = None

    def enable_filelogging(self, filename):
        if self._file_handler is not None:
            self.disable_filelogging()
        clean_name = os.path.expanduser(str(filename or '').strip().strip("'\""))
        if not clean_name:
            clean_name = os.path.join(conf_dir(), 'kblueproximity.log')
        self.filename = clean_name
        try:
            directory = os.path.dirname(clean_name)
            if directory:
                os.makedirs(directory, exist_ok=True)
            handler = logging.FileHandler(clean_name, mode='a', encoding='utf-8')
            handler.setFormatter(
                logging.Formatter('%(asctime)s kblueproximity: %(message)s'))
            self._logger.addHandler(handler)
            self._file_handler = handler
            self.filelogging = True
        except OSError:
            print(_("Could not open logfile '{}' for writing.").format(clean_name))
            self.disable_filelogging()

    def disable_filelogging(self):
        if self._file_handler is not None:
            try:
                self._logger.removeHandler(self._file_handler)
                self._file_handler.close()
            except Exception:
                pass
            self._file_handler = None
        self.filelogging = False
        self.filename = ''

    def log_line(self, line):
        disable_syslog = False
        disable_filelog = False
        with self._log_lock:
            record = self._make_record(line)
            if record.levelno < self._logger.getEffectiveLevel():
                return
            if not self._logger.filter(record):
                return
            for handler in list(self._logger.handlers):
                try:
                    handler.handle(record)
                except Exception:
                    if handler is self._syslog_handler:
                        disable_syslog = True
                    elif handler is self._file_handler:
                        disable_filelog = True
                    else:
                        try:
                            self._logger.removeHandler(handler)
                            handler.close()
                        except Exception:
                            pass
        if disable_syslog:
            self.disable_syslogging()
        if disable_filelog:
            self.disable_filelogging()

    def debug_line(self, config, line):
        if config.get('debug_log', True):
            self.log_line('[debug] ' + line)

    def configureFromConfig(self, config):
        if config['log_to_syslog']:
            self.enable_syslogging(config['log_syslog_facility'])
        else:
            self.disable_syslogging()
        if config['log_to_file']:
            if self.filelogging and config['log_filelog_filename'] != self.filename:
                self.disable_filelogging()
                self.enable_filelogging(config['log_filelog_filename'])
            elif not self.filelogging:
                self.enable_filelogging(config['log_filelog_filename'])
