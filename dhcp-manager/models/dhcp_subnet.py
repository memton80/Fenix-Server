"""Modèle de plage (subnet) DHCP Kea."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DhcpSubnet:
    """Plage DHCP (subnet) déclarée dans la configuration Kea.

    Attributes:
        subnet_id: Identifiant numérique du subnet dans Kea.
        subnet: Réseau au format CIDR (ex. ``192.168.1.0/24``).
        pool: Plage d'attribution (ex. ``192.168.1.100-192.168.1.200``),
            vide si aucune n'est définie.
    """

    subnet_id: int
    subnet: str
    pool: str

    @classmethod
    def from_kea(cls, payload: dict[str, object]) -> DhcpSubnet:
        """Construit un :class:`DhcpSubnet` depuis un objet subnet Kea.

        Args:
            payload: Élément de la liste ``subnet4`` de la configuration Kea.

        Returns:
            La plage correspondante.
        """
        pools = payload.get("pools") or []
        pool = ""
        if pools and isinstance(pools[0], dict):
            pool = str(pools[0].get("pool", ""))
        return cls(
            subnet_id=int(payload.get("id", 0)),
            subnet=str(payload.get("subnet", "")),
            pool=pool,
        )
