# coding=utf-8
"""Shared, user-consented Dahua connection preferences for all demos."""
import os

from PyQt5.QtCore import QSettings


_ORGANIZATION = 'DNC'
_APPLICATION = 'DahuaControlCenter'
_PREFIX = 'connection/'


def settings():
    return QSettings(_ORGANIZATION, _APPLICATION)


def load_connection():
    """Return the previously consented recorder details, or deployment defaults."""
    store = settings()
    return {
        'host': store.value(_PREFIX + 'host', os.getenv('DAHUA_HOST', '')),
        'port': store.value(_PREFIX + 'port', os.getenv('DAHUA_PORT', '37777')),
        'username': store.value(_PREFIX + 'username', os.getenv('DAHUA_USERNAME', '')),
        'password': store.value(_PREFIX + 'password', ''),
        'remember': store.value(_PREFIX + 'remember', False, type=bool),
    }


def save_connection(host, port, username, password):
    store = settings()
    store.setValue(_PREFIX + 'remember', True)
    store.setValue(_PREFIX + 'host', host.strip())
    store.setValue(_PREFIX + 'port', port.strip())
    store.setValue(_PREFIX + 'username', username.strip())
    store.setValue(_PREFIX + 'password', password)
    store.sync()


def clear_connection():
    store = settings()
    store.remove('connection')
    store.sync()
