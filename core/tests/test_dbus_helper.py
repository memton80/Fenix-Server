"""Tests pour core.dbus_helper — le bus système D-Bus est entièrement mocké."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from dasbus.error import DBusError

from core import dbus_helper


# --- get_system_bus -------------------------------------------------------


def test_get_system_bus_retourne_la_connexion():
    """get_system_bus instancie un SystemMessageBus et force la connexion."""
    fake_bus = MagicMock()
    fake_bus.connection = MagicMock()

    with patch.object(dbus_helper, "SystemMessageBus", return_value=fake_bus) as ctor:
        bus = dbus_helper.get_system_bus()

    ctor.assert_called_once_with()
    assert bus is fake_bus


def test_get_system_bus_bus_absent_leve_runtimeerror():
    """Une DBusError à la connexion est convertie en RuntimeError."""
    fake_bus = MagicMock()
    type(fake_bus).connection = property(
        lambda self: (_ for _ in ()).throw(DBusError("pas de bus"))
    )

    with patch.object(dbus_helper, "SystemMessageBus", return_value=fake_bus):
        with pytest.raises(RuntimeError, match="indisponible"):
            dbus_helper.get_system_bus()


# --- get_session_bus ------------------------------------------------------


def test_get_session_bus_retourne_la_connexion():
    """get_session_bus instancie un SessionMessageBus et force la connexion."""
    fake_bus = MagicMock()
    fake_bus.connection = MagicMock()

    with patch.object(dbus_helper, "SessionMessageBus", return_value=fake_bus) as ctor:
        bus = dbus_helper.get_session_bus()

    ctor.assert_called_once_with()
    assert bus is fake_bus


def test_get_session_bus_bus_absent_leve_runtimeerror():
    """Une DBusError à la connexion de session est convertie en RuntimeError."""
    fake_bus = MagicMock()
    type(fake_bus).connection = property(
        lambda self: (_ for _ in ()).throw(DBusError("pas de bus"))
    )

    with patch.object(dbus_helper, "SessionMessageBus", return_value=fake_bus):
        with pytest.raises(RuntimeError, match="session"):
            dbus_helper.get_session_bus()


# --- service_available ----------------------------------------------------


def test_service_available_service_actif():
    """Un service avec un propriétaire sur le bus est disponible."""
    daemon = MagicMock()
    daemon.NameHasOwner.return_value = True
    fake_bus = MagicMock(proxy=daemon)

    with patch.object(dbus_helper, "get_system_bus", return_value=fake_bus):
        assert dbus_helper.service_available("org.freedesktop.PackageKit") is True

    daemon.NameHasOwner.assert_called_once_with("org.freedesktop.PackageKit")
    daemon.ListActivatableNames.assert_not_called()


def test_service_available_service_activable():
    """Un service sans propriétaire mais activable est disponible."""
    daemon = MagicMock()
    daemon.NameHasOwner.return_value = False
    daemon.ListActivatableNames.return_value = ["org.freedesktop.home1"]
    fake_bus = MagicMock(proxy=daemon)

    with patch.object(dbus_helper, "get_system_bus", return_value=fake_bus):
        assert dbus_helper.service_available("org.freedesktop.home1") is True


def test_service_available_service_inconnu():
    """Un service ni actif ni activable n'est pas disponible."""
    daemon = MagicMock()
    daemon.NameHasOwner.return_value = False
    daemon.ListActivatableNames.return_value = ["org.freedesktop.systemd1"]
    fake_bus = MagicMock(proxy=daemon)

    with patch.object(dbus_helper, "get_system_bus", return_value=fake_bus):
        assert dbus_helper.service_available("org.inexistant.Service") is False


def test_service_available_erreur_dbus_retourne_false():
    """Une DBusError pendant la vérification ne propage pas et retourne False."""
    daemon = MagicMock()
    daemon.NameHasOwner.side_effect = DBusError("boom")
    fake_bus = MagicMock(proxy=daemon)

    with patch.object(dbus_helper, "get_system_bus", return_value=fake_bus):
        assert dbus_helper.service_available("org.freedesktop.PackageKit") is False


# --- get_service_proxy ----------------------------------------------------


def test_get_service_proxy_service_disponible():
    """Le proxy est obtenu via le bus quand le service est disponible."""
    proxy = MagicMock()
    fake_bus = MagicMock()
    fake_bus.get_proxy.return_value = proxy

    with patch.object(dbus_helper, "service_available", return_value=True), patch.object(
        dbus_helper, "get_system_bus", return_value=fake_bus
    ):
        result = dbus_helper.get_service_proxy(
            "org.freedesktop.PackageKit", "/org/freedesktop/PackageKit"
        )

    assert result is proxy
    fake_bus.get_proxy.assert_called_once_with(
        "org.freedesktop.PackageKit", "/org/freedesktop/PackageKit"
    )


def test_get_service_proxy_service_indisponible_leve_runtimeerror():
    """Un service indisponible lève RuntimeError sans tenter d'obtenir le proxy."""
    fake_bus = MagicMock()

    with patch.object(dbus_helper, "service_available", return_value=False), patch.object(
        dbus_helper, "get_system_bus", return_value=fake_bus
    ):
        with pytest.raises(RuntimeError, match="indisponible"):
            dbus_helper.get_service_proxy("org.inexistant.Service", "/org/inexistant")

    fake_bus.get_proxy.assert_not_called()
