# -*- coding: utf-8 -*-
"""
Module to interact with HP iLO.

.. versionadded:: x.y.z

:configuration: This module requires the hpilo Python module; additionally it requires
    a login name, password and hostname to connect to the remote system.
    This can either be set in the minion configuration file or via a pillar.

    For example::

        hpilo.login: 'Administrator'
        hpilo.password: 'password'
        hpilo.hostname: 'server1-ilo.oob.local'

    Under most circumstances multiple systems would be managed in which case the configuration
    can be set up as different configuration profiles.

    For example::

        server1-ilo:
          hpilo.login: 'Administrator'
          hpilo.password: 'password_1'
          hpilo.hostname: 'server1-ilo.oob.local'
        server2-ilo
          hpilo.login: 'Administrator'
          hpilo.password: 'password_2'
          hpilo.hostname: 'server2-ilo.oob.local'

    To use a particular host profile pass the `host` parameter:

    .. code-block:: bash

        salt '*' hpilo.get_fw_version profile=server2-ilo

    Finally, these parameters may be passed directly as paramters:

    .. code-block:: bash

        salt '*' hpilo.get_fw_version hostname=server1-ilo login=Administrator password=password
"""

from __future__ import absolute_import, print_function, unicode_literals

import logging
import re

try:
    import hpilo
    HAVE_HPILO = True
except ImportError:
    HAVE_HPILO = False

log = logging.getLogger(__name__)

__opts__ = {}
__virtualname__ = 'hpilo'

def __virtual__():
    """
    Ensure python-hpilo is available.
    """
    if HAVE_HPILO:
        return __virtualname__
    else:
        return False, 'The hpilo execution module cannot be loaded: required hpilo module not found.'


def _login(delay=False, **kwargs):
    """
    Helper function for handling iLO credentials and establishing the connection.
    """
    if all (k in kwargs for k in ('login', 'password', 'hostname')):
        creds = {'login': config['login'], 'password': config['password'], 'hostname': config['hostname']}
    elif 'profile' in kwargs:
        # use the host profile
        profile = __salt__['config.option'](kwargs['profile'])
        creds = {
            'login': profile['login'],
            'password': profile['password'],
            'hostname': profile['hostname'],
        }
    else:
        # Finally use the minion configuration
        creds = {
            'login': __salt__['config.option']('hpilo.login'),
            'password': __salt__['config.option']('hpilo.password'),
            'hostname': __salt__['config.option']('hpilo.hostname'),
        }

    return hpilo.Ilo(**creds, delayed=delay)

def get_power_status(**kwargs):
    """
    Get the current power status.
    """
    ilo = _login(**kwargs)

    try:
        pwr = ilo.get_host_power_status()
    except hpilo.IloError as e:
        log.error(f'Failed to get power state of {ilo.hostname}: {e}')
        return {}

    return { 'power': True if pwr == 'ON' else False }

def power_on(**kwargs):
    """
    Power on the system.
    """
    ret = { 'power_state': True }
    ilo = _login(**kwargs)

    try:
        pwr = ilo.set_host_power(True)
    except IloError as e:
        log.error(f'Failed to power on {ilo.hostname}: {e}')
        return {}

def power_off(hold=False, **kwargs):
    """
    Power off the system. By default performs the equivalent of pressing the power button
    and let the operating system handle the event.

    :param hold: Bool to simulate holding the button to force a shut down
    :param kwargs:
        - profile=host_profile
        - hostname=host
        - login=Administrator
        - password=secret

    :returns dict -- `power_state` (True for 'ON', or False for 'OFF').

    CLI examples:

    .. code-block:: bash

        salt-call hpilo.power_off profile=server1-ilo
    """
    ret = { 'power_state': False}
    ilo = _login(**kwargs)

    # First get the current power state, because if the system is powered off and we
    # press the button, it'll power on.
    if get_power_status(**kwargs).get('power') == False:
        return ret

    try:
        if hold:
            ilo.hold_pwr_btn()
        else:
            ilo.press_pwr_btn()

        return ret
    except hpilo.IloError as e:
        log.error(f'Failed to power off {ilo.hostname}: {e}')
        return {'power_state': None}

def list_users(**kwargs):
    """
    Query the device for all configured users.

    :param kwargs:
        - profile=host_profile
        - hostname=host
        - login=Administrator
        - password=secret
        - detailed=True

    :returns dict/list -- either the list of user names or if `detailed` was set,
        the dict of users returned by the hpilo `get_all_user_info()` call.

    CLI examples:

    .. code-block:: bash

        salt-call hpilo.list_users profile=server1-ilo detailed=True
    """
    ilo = _login(**kwargs)

    try:
        if kwargs.get('detailed'):
            return ilo.get_all_user_info()
        else:
            return ilo.get_all_users()
    except hpilo.IloError as e:
        log.error(f'Failed to get all users from {ilo.hostname}: {e}')
        return {}

def product_info(**kwargs):
    """
    Query the device for the product name and firmware information.

    :param kwargs:
        - profile=host_profile
        - hostname=host
        - login=Administrator
        - password=secret

    :returns dict -- product name, firmware revision details and asset tag

    CLI examples:

    .. code-block:: bash

        salt-call hpilo.get_product_info profile=server1-ilo
    """
    ilo = _login(**kwargs)

    try:
        product_name = ilo.get_product_name()
        fw_version = ilo.get_fw_version()
        asset_tag = ilo.get_asset_tag()
    except hpilo.IloError as e:
        log.error(f'Failed to get product name and version version from {ilo.hostname}: {e}')
        return {}

    return {
        'product_name': product_name,
        **asset_tag,
        **fw_version,
    }

def network_settings(**kwargs):
    """
    Query the device for network settings

    :param kwargs:
        - profile=host_profile
        - hostname=host
        - login=Administrator
        - password=secret

    :returns dict -- all keys returned by the hpilo `get_network_settings` call.

    CLI examples:

    .. code-block:: bash

        salt-call hpilo.get_product_info profile=server1-ilo
    """
    ilo = _login(**kwargs)

    try:
        return ilo.get_network_settings()
    except hpilo.IloError as e:
        log.error(f'Failed to get network settings from {ilo.hostname}: {e}')
        return {}

def get_boot_order(**kwargs):
    """
    Query the device for the persistent boot order of the host.

    :param kwargs:
        - profile=host_profile
        - hostname=host
        - login=Administrator
        - password=secret

    :returns list -- names of boot devices, in sequence

    CLI examples:

    .. code-block:: bash

        salt-call hpilo.get_boot_order profile=server1-ilo
    """
    ilo = _login(**kwargs)

    try:
        return ilo.get_persistent_boot()
    except hpilo.IloError as e:
        log.error(f'Failed to get boot order from {ilo.hostname}: {e}')
        return {}
