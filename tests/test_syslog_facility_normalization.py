from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from kblueproximity import config as config_module
from kblueproximity.config import load_configs
from kblueproximity.paths import conf_dir


class SyslogFacilityNormalizationTests(unittest.TestCase):
    def _write_config(
        self,
        value: str,
        logfile: str | None = None,
        proximity_command: str | None = None,
    ) -> None:
        os.makedirs(conf_dir(), exist_ok=True)
        with open(os.path.join(conf_dir(), 'standard.conf'), 'w', encoding='utf-8') as handle:
            handle.write(f"log_syslog_facility = {value}\n")
            if logfile is not None:
                handle.write(f"log_filelog_filename = {logfile}\n")
            if proximity_command is not None:
                handle.write(f"proximity_command = {proximity_command}\n")

    def _load_config(self):
        configs, _is_new = load_configs()
        return configs[0][1]

    def _load_facility(self) -> str:
        return str(self._load_config()['log_syslog_facility'])

    def test_quoted_valid_facility_is_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': tmp}, clear=False):
                self._write_config("'local7'")
                self.assertEqual(self._load_facility(), 'local7')

    def test_invalid_facility_falls_back_to_local7(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': tmp}, clear=False):
                self._write_config('not_a_facility')
                self.assertEqual(self._load_facility(), 'local7')

    def test_legacy_logfile_path_is_moved_to_xdg(self):
        with tempfile.TemporaryDirectory() as tmp:
            with tempfile.TemporaryDirectory() as home:
                with patch.dict(
                    os.environ,
                    {'XDG_CONFIG_HOME': tmp, 'HOME': home},
                    clear=False,
                ):
                    legacy = os.path.join(home, '.kblueproximity', 'kblueproximity.log')
                    self._write_config('local7', f"'{legacy}'")
                    cfg = self._load_config()
                    self.assertEqual(
                        str(cfg['log_filelog_filename']),
                        os.path.join(conf_dir(), 'kblueproximity.log'),
                    )

    def test_blueproximity_legacy_logfile_path_is_moved_to_xdg(self):
        with tempfile.TemporaryDirectory() as tmp:
            with tempfile.TemporaryDirectory() as home:
                with patch.dict(
                    os.environ,
                    {'XDG_CONFIG_HOME': tmp, 'HOME': home},
                    clear=False,
                ):
                    legacy = os.path.join(home, '.blueproximity', 'kblueproximity.log')
                    self._write_config('local7', legacy)
                    cfg = self._load_config()
                    self.assertEqual(
                        str(cfg['log_filelog_filename']),
                        os.path.join(conf_dir(), 'kblueproximity.log'),
                    )

    def test_new_default_proximity_command_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': tmp}, clear=False):
                cfg = self._load_config()
                self.assertEqual(str(cfg['proximity_command']), '')

    def test_quoted_empty_proximity_command_is_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': tmp}, clear=False):
                self._write_config('local7', proximity_command="''")
                cfg = self._load_config()
                self.assertEqual(str(cfg['proximity_command']), '')

    def test_empty_logfile_value_defaults_to_xdg_logfile(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': tmp}, clear=False):
                self._write_config('local7', logfile="''")
                cfg = self._load_config()
                self.assertEqual(
                    str(cfg['log_filelog_filename']),
                    config_module._default_log_file,
                )


if __name__ == '__main__':
    unittest.main()
