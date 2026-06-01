"""Tests pour models.role_status."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from models.role_status import RoleStatus

from core.roles import Role


def _role() -> Role:
    return Role(
        id="ad",
        name="Active Directory",
        description="Gestion AD/Samba",
        service_name="smbd",
        service_type="systemd",
        app="ad-manager",
    )


def test_role_status_porte_le_role_et_l_etat():
    role = _role()
    status = RoleStatus(role=role, active=True)
    assert status.role is role
    assert status.active is True


def test_role_status_est_frozen():
    status = RoleStatus(role=_role(), active=False)
    with pytest.raises(FrozenInstanceError):
        status.active = True  # type: ignore[misc]


def test_role_status_egalite_par_valeur():
    role = _role()
    assert RoleStatus(role=role, active=True) == RoleStatus(role=role, active=True)
    assert RoleStatus(role=role, active=True) != RoleStatus(role=role, active=False)
