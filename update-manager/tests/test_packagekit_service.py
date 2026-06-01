"""Tests pour services.packagekit_service — D-Bus, Polkit et Qt mockés.

Les transactions PackageKit étant asynchrones, on récupère les handlers
connectés aux signaux D-Bus (``tx.Signal.connect``) et on les invoque
manuellement pour simuler les événements du démon.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from dasbus.error import DBusError
from models.update_item import SystemPackageUpdate
from services import packagekit_service as pk
from services.packagekit_service import PackageKitService

# La QApplication partagée (fixture `qapp` du conftest) suffit pour émettre et
# connecter les signaux Qt.


def _make_bus(manager: MagicMock, transaction: MagicMock, tx_path: str = "/tx/1") -> MagicMock:
    """Bus système factice : get_proxy renvoie le manager puis la transaction."""
    manager.CreateTransaction.return_value = tx_path
    bus = MagicMock()
    bus.get_proxy.side_effect = lambda service, path: (
        manager if path == pk.PACKAGEKIT_OBJECT else transaction
    )
    return bus


def _build_service(bus: MagicMock, *, available: bool = True, authorized: bool = True):
    """Construit un PackageKitService avec bus, Polkit et dispo PackageKit patchés."""
    polkit_instance = MagicMock()
    polkit_instance.check_authorization.return_value = authorized
    ctx = (
        patch.object(pk, "service_available", return_value=available),
        patch.object(pk, "get_system_bus", return_value=bus),
        patch.object(pk, "PolkitClient", return_value=polkit_instance),
    )
    for p in ctx:
        p.start()
    service = PackageKitService()
    return service, polkit_instance, ctx


def _stop(ctx) -> None:
    for p in ctx:
        p.stop()


def _handler(signal_mock: MagicMock):
    """Retourne le dernier callback passé à signal.connect(...)."""
    return signal_mock.connect.call_args.args[0]


# --- request_updates ------------------------------------------------------


def test_request_updates_emet_updates_found():
    manager, transaction = MagicMock(), MagicMock()
    bus = _make_bus(manager, transaction)
    service, _, ctx = _build_service(bus)
    try:
        received: list = []
        service.updates_found.connect(received.append)

        service.request_updates()
        transaction.GetUpdates.assert_called_once_with(pk._FILTER_NONE)

        on_package = _handler(transaction.Package)
        on_finished = _handler(transaction.Finished)
        on_package(11, "bash;5.2-1;amd64;debian", "GNU Bash")
        on_package(11, "vim;9.0;amd64;debian", "Vi IMproved")
        on_finished(1, 0)

        assert len(received) == 1
        updates = received[0]
        assert updates[0] == SystemPackageUpdate(
            "bash;5.2-1;amd64;debian", "bash", "5.2-1", "GNU Bash"
        )
        assert updates[1].name == "vim"
    finally:
        _stop(ctx)


def test_request_updates_packagekit_indisponible_emet_error():
    manager, transaction = MagicMock(), MagicMock()
    bus = _make_bus(manager, transaction)
    service, _, ctx = _build_service(bus, available=False)
    try:
        errors: list = []
        service.error_occurred.connect(errors.append)

        service.request_updates()

        assert errors and "PackageKit" in errors[0]
        bus.get_proxy.assert_not_called()
        transaction.GetUpdates.assert_not_called()
    finally:
        _stop(ctx)


def test_error_code_emet_error_occurred():
    manager, transaction = MagicMock(), MagicMock()
    bus = _make_bus(manager, transaction)
    service, _, ctx = _build_service(bus)
    try:
        errors: list = []
        service.error_occurred.connect(errors.append)

        service.request_updates()
        on_error = _handler(transaction.ErrorCode)
        on_error(4, "dépôt injoignable")

        assert errors == ["dépôt injoignable"]
    finally:
        _stop(ctx)


# --- install_updates ------------------------------------------------------


def test_install_updates_refuse_par_polkit_leve_permissionerror():
    manager, transaction = MagicMock(), MagicMock()
    bus = _make_bus(manager, transaction)
    service, polkit_instance, ctx = _build_service(bus, authorized=False)
    try:
        with pytest.raises(PermissionError):
            service.install_updates(["bash;5.2-1;amd64;debian"])

        polkit_instance.check_authorization.assert_called_once_with(
            pk.POLKIT_ACTION_INSTALL_SYSTEM
        )
        bus.get_proxy.assert_not_called()
    finally:
        _stop(ctx)


def test_install_updates_autorise_emet_progress_et_finished():
    manager, transaction = MagicMock(), MagicMock()
    bus = _make_bus(manager, transaction)
    service, _, ctx = _build_service(bus, authorized=True)
    try:
        progress: list = []
        finished: list = []
        service.progress_changed.connect(progress.append)
        service.finished.connect(lambda: finished.append(True))

        service.install_updates(["bash;5.2-1;amd64;debian"])
        transaction.UpdatePackages.assert_called_once_with(
            pk._TRANSACTION_FLAG_NONE, ["bash;5.2-1;amd64;debian"]
        )

        on_props = _handler(transaction.PropertiesChanged)
        on_finished = _handler(transaction.Finished)
        on_props("org.freedesktop.PackageKit.Transaction", {"Percentage": 42}, [])
        on_finished(1, 0)

        assert progress == [42]
        assert finished == [True]
    finally:
        _stop(ctx)


def test_progress_ignore_les_valeurs_hors_bornes():
    manager, transaction = MagicMock(), MagicMock()
    bus = _make_bus(manager, transaction)
    service, _, ctx = _build_service(bus, authorized=True)
    try:
        progress: list = []
        service.progress_changed.connect(progress.append)

        service.install_updates(["bash;5.2-1;amd64;debian"])
        on_props = _handler(transaction.PropertiesChanged)
        on_props("iface", {"Percentage": 101}, [])  # 101 = inconnu pour PackageKit
        on_props("iface", {"AutreProp": 5}, [])  # propriété sans rapport

        assert progress == []
    finally:
        _stop(ctx)


def test_progress_deballe_un_variant():
    manager, transaction = MagicMock(), MagicMock()
    bus = _make_bus(manager, transaction)
    service, _, ctx = _build_service(bus, authorized=True)
    try:
        progress: list = []
        service.progress_changed.connect(progress.append)

        service.install_updates(["bash;5.2-1;amd64;debian"])
        on_props = _handler(transaction.PropertiesChanged)

        variant = MagicMock()
        variant.unpack.return_value = 77
        on_props("iface", {"Percentage": variant}, [])

        assert progress == [77]
    finally:
        _stop(ctx)


# --- refresh_cache --------------------------------------------------------


def test_refresh_cache_lance_la_transaction_et_signale_la_fin():
    manager, transaction = MagicMock(), MagicMock()
    bus = _make_bus(manager, transaction)
    service, _, ctx = _build_service(bus)
    try:
        finished: list = []
        service.finished.connect(lambda: finished.append(True))

        service.refresh_cache()
        transaction.RefreshCache.assert_called_once_with(False)

        on_finished = _handler(transaction.Finished)
        on_finished(1, 0)
        assert finished == [True]
    finally:
        _stop(ctx)


def test_create_transaction_erreur_dbus_emet_error_sans_propager():
    """Une DBusError lors de CreateTransaction est émise via error_occurred."""
    manager, transaction = MagicMock(), MagicMock()
    manager.CreateTransaction.side_effect = DBusError("boom")
    bus = MagicMock()
    bus.get_proxy.side_effect = lambda service, path: manager
    # service_available=True pour atteindre CreateTransaction.
    service, _, ctx = _build_service(bus, available=True)
    try:
        errors: list = []
        service.error_occurred.connect(errors.append)

        service.request_updates()  # ne doit pas lever

        assert errors and "boom" in errors[0]
        transaction.GetUpdates.assert_not_called()
    finally:
        _stop(ctx)
