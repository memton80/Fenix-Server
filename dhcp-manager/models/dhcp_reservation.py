"""Modèle de réservation DHCP (MAC → IP) Kea."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DhcpReservation:
    """Réservation DHCP associant une adresse MAC à une IP fixe.

    Attributes:
        mac_address: Adresse MAC du client (``hw-address``).
        ip_address: Adresse IP réservée (``ip-address``).
        hostname: Nom d'hôte associé, vide si absent.
        subnet_id: Identifiant du subnet auquel la réservation est rattachée.
    """

    mac_address: str
    ip_address: str
    hostname: str
    subnet_id: int

    @classmethod
    def from_kea(cls, payload: dict[str, object], subnet_id: int) -> DhcpReservation:
        """Construit une :class:`DhcpReservation` depuis un objet réservation Kea.

        Args:
            payload: Élément de la liste ``reservations`` d'un subnet.
            subnet_id: Identifiant du subnet contenant la réservation.

        Returns:
            La réservation correspondante.
        """
        return cls(
            mac_address=str(payload.get("hw-address", "")),
            ip_address=str(payload.get("ip-address", "")),
            hostname=str(payload.get("hostname", "")),
            subnet_id=subnet_id,
        )

    def to_kea(self) -> dict[str, object]:
        """Sérialise la réservation au format attendu par ``reservation-add``.

        Returns:
            Le mapping ``hw-address``/``ip-address``/``hostname``.
        """
        payload: dict[str, object] = {
            "hw-address": self.mac_address,
            "ip-address": self.ip_address,
        }
        if self.hostname:
            payload["hostname"] = self.hostname
        return payload
