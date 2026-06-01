"""Tests pour services.kea_service — API REST (urllib) et subprocess mockés."""

from __future__ import annotations

import base64
import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from models.dhcp_reservation import DhcpReservation
from services.kea_service import KeaService


def _http_response(body: object) -> MagicMock:
    """Simule un contexte ``urlopen`` renvoyant ``body`` encodé en JSON."""
    payload = json.dumps(body).encode("utf-8")
    response = MagicMock()
    response.read.return_value = payload
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


def _ok(arguments: dict) -> list:
    return [{"result": 0, "arguments": arguments}]


def _service(password: str = "") -> KeaService:
    """Service Kea déterministe : mot de passe explicite, sans accès fichier."""
    return KeaService(password=password)


def test_list_leases_mappe_la_reponse():
    service = _service()
    body = _ok(
        {
            "leases": [
                {
                    "ip-address": "192.168.1.10",
                    "hw-address": "aa:bb:cc:dd:ee:ff",
                    "hostname": "pc1",
                    "state": 0,
                }
            ]
        }
    )
    with patch("urllib.request.urlopen", return_value=_http_response(body)):
        leases = service.list_leases()
    assert len(leases) == 1
    assert leases[0].ip_address == "192.168.1.10"
    assert leases[0].state == "active"


def test_list_subnets_lit_la_config():
    service = _service()
    body = _ok(
        {
            "Dhcp4": {
                "subnet4": [
                    {
                        "id": 1,
                        "subnet": "192.168.1.0/24",
                        "pools": [{"pool": "192.168.1.100-192.168.1.200"}],
                    }
                ]
            }
        }
    )
    with patch("urllib.request.urlopen", return_value=_http_response(body)):
        subnets = service.list_subnets()
    assert subnets[0].subnet_id == 1
    assert subnets[0].pool == "192.168.1.100-192.168.1.200"


def test_add_reservation_envoie_la_commande():
    service = _service()
    reservation = DhcpReservation("aa:bb:cc:dd:ee:ff", "192.168.1.50", "pc2", subnet_id=1)
    captured: dict = {}

    def _capture(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _http_response(_ok({}))

    with patch("urllib.request.urlopen", side_effect=_capture):
        service.add_reservation(reservation)

    assert captured["payload"]["command"] == "reservation-add"
    assert captured["payload"]["arguments"]["reservation"]["subnet-id"] == 1
    assert captured["payload"]["arguments"]["reservation"]["ip-address"] == "192.168.1.50"


def test_command_erreur_kea_leve_runtimeerror():
    service = _service()
    body = [{"result": 1, "text": "boom"}]
    with (
        patch("urllib.request.urlopen", return_value=_http_response(body)),
        pytest.raises(RuntimeError),
    ):
        service.list_leases()


# --- authentification HTTP basic -------------------------------------------


def test_command_envoie_l_entete_authorization():
    service = KeaService(username="fenix", password="s3cret")
    captured: dict = {}

    def _capture(request, timeout):
        captured["auth"] = request.get_header("Authorization")
        return _http_response(_ok({}))

    with patch("urllib.request.urlopen", side_effect=_capture):
        service.list_leases()

    expected = "Basic " + base64.b64encode(b"fenix:s3cret").decode("ascii")
    assert captured["auth"] == expected


def test_mot_de_passe_lu_depuis_le_fichier(tmp_path):
    pw_file = tmp_path / "kea-api-password"
    pw_file.write_text("fromfile\n", encoding="utf-8")
    service = KeaService(password_file=str(pw_file))
    captured: dict = {}

    def _capture(request, timeout):
        captured["auth"] = request.get_header("Authorization")
        return _http_response(_ok({}))

    with patch("urllib.request.urlopen", side_effect=_capture):
        service.list_leases()

    # Le fichier est lu et débarrassé du saut de ligne final.
    expected = "Basic " + base64.b64encode(b"fenix:fromfile").decode("ascii")
    assert captured["auth"] == expected


def test_fichier_absent_aucune_authentification(tmp_path):
    service = KeaService(password_file=str(tmp_path / "absent"))
    captured: dict = {}

    def _capture(request, timeout):
        captured["auth"] = request.get_header("Authorization")
        return _http_response(_ok({}))

    with patch("urllib.request.urlopen", side_effect=_capture):
        service.list_leases()

    assert captured["auth"] is None


# --- contrôle du service ----------------------------------------------------


def test_control_service_via_pkexec_systemctl():
    service = _service()
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    with patch("subprocess.run", return_value=completed) as run:
        service.control_service("restart")
    assert run.call_args.args[0] == [
        "pkexec",
        "systemctl",
        "restart",
        "kea-dhcp4-server",
    ]


def test_control_service_action_invalide_leve_valueerror():
    service = _service()
    with pytest.raises(ValueError):
        service.control_service("frobnicate")
