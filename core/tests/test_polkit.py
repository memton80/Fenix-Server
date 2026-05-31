"""Tests pour core.polkit — bus système et autorité Polkit entièrement mockés."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from dasbus.error import DBusError

from core import polkit
from core.polkit import PolkitClient


def _make_bus(authority: MagicMock, unique_name: str = ":1.42") -> MagicMock:
    """Construit un faux bus système exposant ``get_proxy`` et un nom unique."""
    bus = MagicMock()
    bus.get_proxy.return_value = authority
    bus.connection.get_unique_name.return_value = unique_name
    return bus


def _patch_bus(bus: MagicMock, *, available: bool = True):
    """Patche get_system_bus et service_available dans le module polkit."""
    return (
        patch.object(polkit, "get_system_bus", return_value=bus),
        patch.object(polkit, "service_available", return_value=available),
    )


def test_check_authorization_autorise():
    """CheckAuthorization renvoyant authorized=True donne True."""
    authority = MagicMock()
    authority.CheckAuthorization.return_value = (True, False, {})
    bus = _make_bus(authority)
    p_bus, p_avail = _patch_bus(bus)

    with p_bus, p_avail:
        client = PolkitClient()
        assert client.check_authorization("org.fenixserver.ad.create-user") is True

    # Sujet system-bus-name + action + flag interaction (1).
    args = authority.CheckAuthorization.call_args.args
    assert args[0][0] == "system-bus-name"
    assert args[1] == "org.fenixserver.ad.create-user"
    assert args[3] == 1  # AllowUserInteraction


def test_check_authorization_refuse():
    """CheckAuthorization renvoyant authorized=False donne False."""
    authority = MagicMock()
    authority.CheckAuthorization.return_value = (False, False, {})
    bus = _make_bus(authority)
    p_bus, p_avail = _patch_bus(bus)

    with p_bus, p_avail:
        client = PolkitClient()
        assert client.check_authorization("org.fenixserver.ad.delete-user") is False


def test_check_authorization_sans_interaction_passe_flag_zero():
    """allow_interaction=False envoie le flag 0 (aucune invite)."""
    authority = MagicMock()
    authority.CheckAuthorization.return_value = (False, True, {})
    bus = _make_bus(authority)
    p_bus, p_avail = _patch_bus(bus)

    with p_bus, p_avail:
        client = PolkitClient()
        client.check_authorization("org.fenixserver.ad.create-user", allow_interaction=False)

    assert authority.CheckAuthorization.call_args.args[3] == 0


def test_check_authorization_erreur_dbus_leve_runtimeerror():
    """Une DBusError de l'autorité est convertie en RuntimeError."""
    authority = MagicMock()
    authority.CheckAuthorization.side_effect = DBusError("boom")
    bus = _make_bus(authority)
    p_bus, p_avail = _patch_bus(bus)

    with p_bus, p_avail:
        client = PolkitClient()
        with pytest.raises(RuntimeError, match="Vérification Polkit impossible"):
            client.check_authorization("org.fenixserver.ad.create-user")


def test_check_authorization_polkit_indisponible_leve_runtimeerror():
    """Si le service Polkit est absent, RuntimeError sans appeler get_proxy."""
    authority = MagicMock()
    bus = _make_bus(authority)
    p_bus, p_avail = _patch_bus(bus, available=False)

    with p_bus, p_avail:
        client = PolkitClient()
        with pytest.raises(RuntimeError, match="Polkit indisponible"):
            client.check_authorization("org.fenixserver.ad.create-user")

    bus.get_proxy.assert_not_called()


def test_authority_cree_une_seule_fois():
    """Le proxy de l'autorité est mis en cache entre deux appels."""
    authority = MagicMock()
    authority.CheckAuthorization.return_value = (True, False, {})
    bus = _make_bus(authority)
    p_bus, p_avail = _patch_bus(bus)

    with p_bus, p_avail:
        client = PolkitClient()
        client.check_authorization("org.fenixserver.ad.create-user")
        client.check_authorization("org.fenixserver.ad.delete-user")

    bus.get_proxy.assert_called_once_with(polkit.POLKIT_SERVICE, polkit.POLKIT_OBJECT)


def test_is_challenge_renvoie_le_flag_challenge():
    """is_challenge renvoie le second champ du résultat et n'autorise pas l'interaction."""
    authority = MagicMock()
    authority.CheckAuthorization.return_value = (False, True, {})
    bus = _make_bus(authority)
    p_bus, p_avail = _patch_bus(bus)

    with p_bus, p_avail:
        client = PolkitClient()
        assert client.is_challenge("org.fenixserver.ad.create-user") is True

    assert authority.CheckAuthorization.call_args.args[3] == 0
