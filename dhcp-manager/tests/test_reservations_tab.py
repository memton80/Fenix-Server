"""Tests pour l'onglet Réservations (service mocké)."""

from __future__ import annotations

from unittest.mock import MagicMock

from models.dhcp_reservation import DhcpReservation
from models.dhcp_subnet import DhcpSubnet
from widgets.reservations_tab import ReservationsTab

from core.theme import ThemeManager


def _service() -> MagicMock:
    service = MagicMock()
    service.list_subnets.return_value = [DhcpSubnet(1, "192.168.1.0/24", "")]
    service.list_reservations.return_value = [
        DhcpReservation("aa:bb:cc:dd:ee:ff", "192.168.1.50", "pc2", subnet_id=1),
    ]
    return service


def test_reload_subnets_remplit_le_selecteur():
    tab = ReservationsTab(_service(), ThemeManager())
    assert tab._combo_subnet.count() == 1
    assert tab._current_subnet_id() == 1


def test_refresh_liste_les_reservations():
    tab = ReservationsTab(_service(), ThemeManager())
    assert tab._table.rowCount() == 1
    assert tab._table.item(0, 1).text() == "192.168.1.50"


def test_add_reservation_delegue_au_service():
    service = _service()
    tab = ReservationsTab(service, ThemeManager())
    reservation = DhcpReservation("11:22:33:44:55:66", "192.168.1.60", "", subnet_id=1)
    tab._service.add_reservation(reservation)
    service.add_reservation.assert_called_once_with(reservation)
