"""Tests pour services.role_service — RoleRegistry, Polkit et systemd mockés."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from models.role_status import RoleStatus
from services import role_service as rs
from services.role_service import RoleService

from core.roles import Role


def _role(role_id: str, service_name: str) -> Role:
    return Role(
        id=role_id,
        name=role_id.upper(),
        description=f"Rôle {role_id}",
        service_name=service_name,
        service_type="systemd",
        app=f"{role_id}-manager",
    )


def _registry(roles: list[Role], active: dict[str, bool] | None = None) -> MagicMock:
    """Registre factice : all_roles, get(id) et is_active(id) mockés."""
    active = active or {}
    by_id = {role.id: role for role in roles}
    registry = MagicMock()
    registry.all_roles.return_value = roles
    registry.get.side_effect = lambda role_id: by_id[role_id]
    registry.is_active.side_effect = lambda role_id: active.get(role_id, False)
    return registry


def _service(registry: MagicMock, *, authorized: bool = True) -> tuple[RoleService, MagicMock]:
    polkit = MagicMock()
    polkit.check_authorization.return_value = authorized
    return RoleService(registry, polkit=polkit), polkit


# --- list_roles ------------------------------------------------------------


def test_list_roles_construit_les_statuts():
    roles = [_role("ad", "smbd"), _role("updates", "org.freedesktop.PackageKit")]
    registry = _registry(roles, active={"ad": True})
    service, _ = _service(registry)

    statuses = service.list_roles()

    assert statuses == [
        RoleStatus(role=roles[0], active=True),
        RoleStatus(role=roles[1], active=False),
    ]


def test_list_roles_vide():
    service, _ = _service(_registry([]))
    assert service.list_roles() == []


# --- enable_role -----------------------------------------------------------


def test_enable_role_enable_puis_start():
    registry = _registry([_role("ad", "smbd")])
    service, polkit = _service(registry, authorized=True)
    manager = MagicMock()

    with patch.object(rs, "get_service_proxy", return_value=manager) as proxy:
        service.enable_role("ad")

    polkit.check_authorization.assert_called_once_with(rs.POLKIT_ACTION_ENABLE_ROLE)
    proxy.assert_called_once_with(rs.SYSTEMD_SERVICE, rs.SYSTEMD_OBJECT)
    manager.EnableUnitFiles.assert_called_once_with(["smbd.service"], False, True)
    manager.StartUnit.assert_called_once_with("smbd.service", rs._JOB_MODE_REPLACE)


def test_enable_role_refuse_par_polkit_leve_permissionerror():
    registry = _registry([_role("ad", "smbd")])
    service, polkit = _service(registry, authorized=False)

    with patch.object(rs, "get_service_proxy") as proxy:
        with pytest.raises(PermissionError):
            service.enable_role("ad")

    polkit.check_authorization.assert_called_once_with(rs.POLKIT_ACTION_ENABLE_ROLE)
    proxy.assert_not_called()  # vérif Polkit AVANT toute action systemd


def test_enable_role_inconnu_leve_keyerror():
    registry = _registry([_role("ad", "smbd")])
    service, polkit = _service(registry)

    with patch.object(rs, "get_service_proxy") as proxy:
        with pytest.raises(KeyError):
            service.enable_role("inexistant")

    polkit.check_authorization.assert_not_called()
    proxy.assert_not_called()


def test_enable_role_normalise_le_nom_d_unite():
    registry = _registry([_role("custom", "monservice.socket")])
    service, _ = _service(registry)
    manager = MagicMock()

    with patch.object(rs, "get_service_proxy", return_value=manager):
        service.enable_role("custom")

    # Un suffixe d'unité connu est conservé tel quel.
    manager.StartUnit.assert_called_once_with("monservice.socket", rs._JOB_MODE_REPLACE)


# --- disable_role ----------------------------------------------------------


def test_disable_role_stop_puis_disable():
    registry = _registry([_role("ad", "smbd")])
    service, polkit = _service(registry, authorized=True)
    manager = MagicMock()

    with patch.object(rs, "get_service_proxy", return_value=manager):
        service.disable_role("ad")

    polkit.check_authorization.assert_called_once_with(rs.POLKIT_ACTION_DISABLE_ROLE)
    manager.StopUnit.assert_called_once_with("smbd.service", rs._JOB_MODE_REPLACE)
    manager.DisableUnitFiles.assert_called_once_with(["smbd.service"], False)


def test_disable_role_refuse_par_polkit_leve_permissionerror():
    registry = _registry([_role("ad", "smbd")])
    service, _ = _service(registry, authorized=False)

    with patch.object(rs, "get_service_proxy") as proxy:
        with pytest.raises(PermissionError):
            service.disable_role("ad")

    proxy.assert_not_called()
