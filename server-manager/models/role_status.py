"""Modèle d'état d'un rôle pour le dashboard du Server Manager."""

from __future__ import annotations

from dataclasses import dataclass

from core.roles import Role


@dataclass(frozen=True)
class RoleStatus:
    """État d'un rôle tel qu'affiché dans le dashboard.

    Attributes:
        role: Définition du rôle (issue de ``core.roles.RoleRegistry``).
        active: ``True`` si le service du rôle tourne actuellement.
    """

    role: Role
    active: bool
