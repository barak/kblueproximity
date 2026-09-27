from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from kblueproximity.logger import Logger


class LoggerTests(unittest.TestCase):
    def test_file_logging_is_disabled_after_handler_failure(self):
        logger = Logger()
        logger.enable_filelogging('/tmp/kblueproximity-test.log')
        self.assertTrue(logger.filelogging)
        with patch.object(logger._file_handler, 'handle', side_effect=OSError('disk full')):
            logger.log_line('message')
        self.assertFalse(logger.filelogging)

    def test_enable_syslogging_falls_back_to_next_socket(self):
        logger = Logger()
        mock_handler = MagicMock()
        with (
            patch.object(logger, '_syslog_addresses', return_value=['/a', '/b']),
            patch('kblueproximity.logger.os.path.exists', return_value=True),
            patch.object(logger, '_is_unix_socket', return_value=True),
            patch(
                'kblueproximity.logger.logging.handlers.SysLogHandler',
                side_effect=[OSError('bad socket'), mock_handler],
            ),
        ):
            logger.enable_syslogging('local7')
        self.assertTrue(logger.syslogging)
        self.assertIs(logger._syslog_handler, mock_handler)

    def test_syslogging_is_disabled_after_handler_failure(self):
        logger = Logger()
        mock_handler = MagicMock()
        with (
            patch.object(logger, '_syslog_addresses', return_value=['/a']),
            patch('kblueproximity.logger.os.path.exists', return_value=True),
            patch.object(logger, '_is_unix_socket', return_value=True),
            patch('kblueproximity.logger.logging.handlers.SysLogHandler', return_value=mock_handler),
        ):
            logger.enable_syslogging('local7')
        self.assertTrue(logger.syslogging)
        with patch.object(mock_handler, 'handle', side_effect=OSError('syslog down')):
            logger.log_line('message')
        self.assertFalse(logger.syslogging)

    def test_syslog_failure_keeps_file_logging_active(self):
        logger = Logger()
        syslog_handler = MagicMock()
        file_handler = MagicMock()
        logger._logger.handlers = [syslog_handler, file_handler]
        logger._syslog_handler = syslog_handler
        logger._file_handler = file_handler
        logger.syslogging = True
        logger.filelogging = True
        syslog_handler.handle.side_effect = OSError('syslog down')
        logger.log_line('message')
        self.assertFalse(logger.syslogging)
        self.assertTrue(logger.filelogging)
        file_handler.handle.assert_called_once()


if __name__ == '__main__':
    unittest.main()
