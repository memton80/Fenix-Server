"""Tests pour services.role_service — RoleRegistry, Polkit et subprocess mockés."""

from __future__ import annotations

import subprocess
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


def test_enable_role_lance_systemctl_enable_now():
    registry = _registry([_role("ad", "smbd")])
    service, polkit = _service(registry, authorized=True)

    with patch("subprocess.run") as run:
        service.enable_role("ad")

    polkit.check_authorization.assert_called_once_with(rs.POLKIT_ACTION_ENABLE_ROLE)
    run.assert_called_once()
    assert run.call_args.args[0] == ["pkexec", "systemctl", "enable", "--now", "smbd.service"]
    assert run.call_args.kwargs["check"] is True


def test_enable_role_refuse_par_polkit_leve_permissionerror():
    registry = _registry([_role("ad", "smbd")])
    service, polkit = _service(registry, authorized=False)

    with patch("subprocess.run") as run:
        with pytest.raises(PermissionError):
            service.enable_role("ad")

    polkit.check_authorization.assert_called_once_with(rs.POLKIT_ACTION_ENABLE_ROLE)
    run.assert_not_called()  # vérif Polkit AVANT toute action systemctl


def test_enable_role_inconnu_leve_keyerror():
    registry = _registry([_role("ad", "smbd")])
    service, polkit = _service(registry)

    with patch("subprocess.run") as run:
        with pytest.raises(KeyError):
            service.enable_role("inexistant")

    polkit.check_authorization.assert_not_called()
    run.assert_not_called()


def test_enable_role_normalise_le_nom_d_unite():
    registry = _registry([_role("custom", "monservice.socket")])
    service, _ = _service(registry)

    with patch("subprocess.run") as run:
        service.enable_role("custom")

    # Un suffixe d'unité connu est conservé tel quel.
    assert run.call_args.args[0] == [
        "pkexec",
        "systemctl",
        "enable",
        "--now",
        "monservice.socket",
    ]


def test_enable_role_echec_systemctl_leve_runtimeerror():
    registry = _registry([_role("ad", "smbd")])
    service, _ = _service(registry, authorized=True)

    err = subprocess.CalledProcessError(1, ["pkexec", "systemctl"], stderr="unit introuvable")
    with patch("subprocess.run", side_effect=err):
        with pytest.raises(RuntimeError, match="systemctl échouée"):
            service.enable_role("ad")


# --- disable_role ----------------------------------------------------------


def test_disable_role_lance_systemctl_disable_now():
    registry = _registry([_role("ad", "smbd")])
    service, polkit = _service(registry, authorized=True)

    with patch("subprocess.run") as run:
        service.disable_role("ad")

    polkit.check_authorization.assert_called_once_with(rs.POLKIT_ACTION_DISABLE_ROLE)
    run.assert_called_once()
    assert run.call_args.args[0] == ["pkexec", "systemctl", "disable", "--now", "smbd.service"]


def test_disable_role_refuse_par_polkit_leve_permissionerror():
    registry = _registry([_role("ad", "smbd")])
    service, _ = _service(registry, authorized=False)

    with patch("subprocess.run") as run:
        with pytest.raises(PermissionError):
            service.disable_role("ad")

    run.assert_not_called()
