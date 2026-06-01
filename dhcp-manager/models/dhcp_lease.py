"""Modèle de bail DHCP (Kea)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DhcpLease:
    """Bail DHCP actif, tel qu'exposé par l'API Kea.

    Attributes:
        ip_address: Adresse IP attribuée.
        mac_address: Adresse MAC du client (``hw-address``).
        hostname: Nom d'hôte annoncé par le client, vide si absent.
        state: État du bail (``active``, ``declined``, ``expired``...).
    """

    ip_address: str
    mac_address: str
    hostname: str
    state: str

    @classmethod
    def from_kea(cls, payload: dict[str, object]) -> DhcpLease:
        """Construit un :class:`DhcpLease` depuis un objet bail de l'API Kea.

        Args:
            payload: Élément de la liste ``leases`` renvoyée par
                ``lease4-get-all``.

        Returns:
            Le bail correspondant.
        """
        state_code = payload.get("state", 0)
        return cls(
            ip_address=str(payload.get("ip-address", "")),
            mac_address=str(payload.get("hw-address", "")),
            hostname=str(payload.get("hostname", "")),
            state=_STATE_LABELS.get(int(state_code), str(state_code)),
        )


# Codes d'état des baux Kea (``state``) vers libellés lisibles.
_STATE_LABELS = {0: "active", 1: "declined", 2: "expired"}
