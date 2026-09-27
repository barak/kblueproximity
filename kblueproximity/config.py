"""ConfigObj specs, defaults, and config loading."""
from __future__ import annotations

import os
import sys

from kblueproximity.i18n import _
from kblueproximity.paths import conf_dir

try:
    from configobj import ConfigObj
    from validate import Validator
except ImportError:
    print(_("The program cannot import the module ConfigObj or Validator."))
    print(_("Please make sure the ConfigObject package for python is installed."))
    print(_("e.g. with Ubuntu Linux, type"))
    print(_(" sudo apt-get install python3-configobj"))
    sys.exit(1)


def get_default_commands():
    """Return lock/unlock/proximity shell commands suited to the current desktop."""
    desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').upper()
    if 'KDE' in desktop:
        return (
            'loginctl lock-session',
            'loginctl unlock-session',
            'qdbus6 org.freedesktop.ScreenSaver /ScreenSaver SimulateUserActivity',
        )
    return (
        'loginctl lock-session',
        'loginctl unlock-session',
        '',
    )


def _conf_string_default(value: str) -> str:
    escaped = value.replace('\\', '\\\\').replace('"', '\\"')
    return f'string(default="{escaped}")'


_default_lock, _default_unlock, _default_proximity = get_default_commands()
_default_log_file = os.path.join(conf_dir(), 'kblueproximity.log')
STANDARD_CONFIG_NAME = 'standard'
STANDARD_CONFIG_FILENAME = STANDARD_CONFIG_NAME + '.conf'

CONF_SPECS = [
    'device_mac=string(max=17,default="")',
    'device_channel=integer(1,30,default=7)',
    'lock_distance=integer(0,127,default=7)',
    'lock_duration=integer(0,120,default=6)',
    'unlock_distance=integer(0,127,default=4)',
    'unlock_duration=integer(0,120,default=1)',
    'lock_command=' + _conf_string_default(_default_lock),
    'unlock_command=' + _conf_string_default(_default_unlock),
    'proximity_command=' + _conf_string_default(_default_proximity),
    'proximity_interval=integer(5,600,default=60)',
    'scan_period=integer(1,60,default=1)',
    'buffer_size=integer(1,255,default=1)',
    'debug_log=boolean(default=True)',
    'log_to_syslog=boolean(default=True)',
    "log_syslog_facility=string(default='local7')",
    'log_to_file=boolean(default=True)',
    'log_filelog_filename=' + _conf_string_default(_default_log_file),
]

LOCK_COMMAND_SUGGESTIONS = [
    'loginctl lock-session',
    'qdbus6 org.freedesktop.ScreenSaver /ScreenSaver Lock',
]
UNLOCK_COMMAND_SUGGESTIONS = [
    'loginctl unlock-session',
]
PROXIMITY_COMMAND_SUGGESTIONS = [
    'qdbus6 org.freedesktop.ScreenSaver /ScreenSaver SimulateUserActivity',
    'xset dpms force on',
]
SYSLOG_FACILITIES = [
    'local0', 'local1', 'local2', 'local3',
    'local4', 'local5', 'local6', 'local7', 'user',
]


def ensure_conf_dir() -> str:
    path = conf_dir()
    home = os.path.expanduser('~')
    legacy_dirs = [
        os.path.join(home, '.kblueproximity'),
        os.path.join(home, '.blueproximity'),
    ]

    copied_legacy_dir = False
    if not os.path.isdir(path):
        for legacy in legacy_dirs:
            if not os.path.isdir(legacy):
                continue
            try:
                import shutil
                shutil.copytree(legacy, path)
                print(_("Copied configuration from '%s' to '%s'.") % (legacy, path))
                copied_legacy_dir = True
                break
            except OSError:
                pass

    created = not os.path.isdir(path)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        return path
    if created:
        print(_("Creating new config directory '%s'.") % path)

    standard_conf = os.path.join(path, STANDARD_CONFIG_FILENAME)
    if not copied_legacy_dir and not os.path.exists(standard_conf):
        validator = Validator()
        for legacy_rc in (
            os.path.join(home, '.blueproximityrc'),
            os.path.join(home, '.kblueproximityrc'),
        ):
            try:
                legacy_config = ConfigObj(
                    legacy_rc,
                    {
                        'create_empty': False,
                        'file_error': True,
                        'configspec': CONF_SPECS,
                    },
                )
                if legacy_config.validate(validator, copy=True) is not True:
                    continue
                legacy_config.filename = standard_conf
                legacy_config.write()
                os.remove(legacy_rc)
                print(_("Moved old configuration to the new config directory."))
                break
            except OSError:
                pass
    return path


def load_configs():
    """Load all *.conf files. Returns (configs, is_new) where configs is
    a list of [name, ConfigObj] (Proximity thread appended later)."""
    directory = ensure_conf_dir()
    home = os.path.expanduser('~')
    vdt = Validator()
    configs = []
    new_config = True

    for filename in os.listdir(directory):
        if not filename.endswith('.conf'):
            continue
        if filename == 'behavior.conf':
            continue
        try:
            config = ConfigObj(
                os.path.join(directory, filename),
                {'create_empty': False, 'file_error': True, 'configspec': CONF_SPECS},
            )
            config.validate(vdt, copy=True)
            changed = False
            facility_raw = str(config.get('log_syslog_facility', ''))
            facility = facility_raw.strip().strip("'\"")
            normalized_facility = facility if facility in SYSLOG_FACILITIES else 'local7'
            if normalized_facility != facility_raw:
                config['log_syslog_facility'] = normalized_facility
                changed = True
            for command_key in ('lock_command', 'unlock_command', 'proximity_command'):
                command_raw = str(config.get(command_key, ''))
                command_clean = command_raw.strip()
                if command_clean in {"''", '""'}:
                    config[command_key] = ''
                    changed = True
            logfile_raw = str(config.get('log_filelog_filename', ''))
            logfile_clean = logfile_raw.strip().strip("'\"")
            logfile_current = os.path.expanduser(logfile_clean) if logfile_clean else ''
            if logfile_clean:
                logfile = os.path.expanduser(logfile_clean)
                logfile_abs = os.path.abspath(logfile)
            else:
                logfile = _default_log_file
                logfile_abs = os.path.abspath(logfile)
            legacy_defaults = (
                os.path.join(home, '.kblueproximity', 'kblueproximity.log'),
                os.path.join(home, '.blueproximity', 'kblueproximity.log'),
            )
            for legacy_default in legacy_defaults:
                if logfile_abs == os.path.abspath(legacy_default):
                    logfile = os.path.join(conf_dir(), 'kblueproximity.log')
                    break
            if logfile != logfile_current:
                config['log_filelog_filename'] = logfile
                changed = True
            if changed:
                config.write()
            configs.append([filename[:-5], config])
            new_config = False
            print(_("Using config file '%s'.") % filename)
        except Exception:
            print(_("'%s' is not a valid config file.") % filename)

    if new_config:
        config = ConfigObj(
            os.path.join(directory, STANDARD_CONFIG_FILENAME),
            {'create_empty': True, 'file_error': False, 'configspec': CONF_SPECS},
        )
        config['device_mac'] = ''
        config.validate(vdt, copy=True)
        config.write()
        configs.append([STANDARD_CONFIG_NAME, config])
        print(_("Creating new configuration."))
        print(_("Using config file '%s'.") % STANDARD_CONFIG_FILENAME)

    configs.sort()
    return configs, new_config
