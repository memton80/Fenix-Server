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


def _response(result: int, text: str = "") -> list:
    return [{"result": result, "text": text}]


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


def test_list_leases_vide_si_resultat_kea_vide():
    # result == 3 (« vide ») : aucun bail, pas une erreur.
    service = _service()
    body = _response(3, "0 IPv4 lease(s) found")
    with patch("urllib.request.urlopen", return_value=_http_response(body)):
        assert service.list_leases() == []


def test_list_leases_vide_si_texte_aucun_bail():
    # Texte « 0 IPv4 lease(s) found » même avec un autre code : traité comme vide.
    service = _service()
    body = _response(1, "0 IPv4 lease(s) found")
    with patch("urllib.request.urlopen", return_value=_http_response(body)):
        assert service.list_leases() == []


def test_list_leases_vraie_erreur_leve_runtimeerror():
    # Une erreur réelle (code 1, autre texte) continue de lever RuntimeError.
    service = _service()
    body = _response(1, "boom")
    with (
        patch("urllib.request.urlopen", return_value=_http_response(body)),
        pytest.raises(RuntimeError),
    ):
        service.list_leases()


# --- plages : lecture/écriture directe de /etc/kea/kea-dhcp4.conf ----------

_DHCP4_CONFIG = "/etc/kea/kea-dhcp4.conf"


def _completed(stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def test_list_subnets_lit_le_fichier_via_pkexec_cat():
    service = _service()
    config = {
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
    with patch("subprocess.run", return_value=_completed(json.dumps(config))) as run:
        subnets = service.list_subnets()
    assert run.call_args.args[0] == ["pkexec", "cat", _DHCP4_CONFIG]
    assert subnets[0].subnet_id == 1
    assert subnets[0].pool == "192.168.1.100-192.168.1.200"


def test_list_subnets_vide_si_subnet4_vide():
    service = _service()
    config = {"Dhcp4": {"subnet4": []}}
    with patch("subprocess.run", return_value=_completed(json.dumps(config))):
        assert service.list_subnets() == []


def test_list_subnets_lecture_echoue_leve_runtimeerror():
    service = _service()
    error = subprocess.CalledProcessError(1, ["pkexec"], stderr="denied")
    with patch("subprocess.run", side_effect=error), pytest.raises(RuntimeError):
        service.list_subnets()


def _run_with_config(config: dict, captured: dict):
    """side_effect : `pkexec cat` renvoie config, `tee` capture le JSON écrit."""

    def _run(cmd, *args, **kwargs):
        if cmd[:2] == ["pkexec", "cat"]:
            return _completed(json.dumps(config))
        if cmd[:2] == ["pkexec", "tee"]:
            captured["written"] = kwargs.get("input")
        captured.setdefault("commands", []).append(cmd)
        return _completed()

    return _run


def test_set_subnet_met_a_jour_le_fichier_et_redemarre():
    service = _service()
    config = {"Dhcp4": {"subnet4": [{"id": 1, "subnet": "192.168.1.0/24", "pools": []}]}}
    captured: dict = {}
    with patch("subprocess.run", side_effect=_run_with_config(config, captured)):
        result = service.set_subnet("192.168.1.0/24", "192.168.1.50-192.168.1.99", subnet_id=1)

    written = json.loads(captured["written"])
    assert written["Dhcp4"]["subnet4"][0]["pools"] == [{"pool": "192.168.1.50-192.168.1.99"}]
    # tee puis redémarrage de kea-dhcp4-server.
    assert ["pkexec", "tee", _DHCP4_CONFIG] in captured["commands"]
    assert ["pkexec", "systemctl", "restart", "kea-dhcp4-server"] in captured["commands"]
    assert result.pool == "192.168.1.50-192.168.1.99"


def test_set_subnet_ajoute_une_plage_absente():
    service = _service()
    config: dict = {"Dhcp4": {"subnet4": []}}
    captured: dict = {}
    with patch("subprocess.run", side_effect=_run_with_config(config, captured)):
        service.set_subnet("10.0.0.0/24", "", subnet_id=5)

    written = json.loads(captured["written"])
    assert written["Dhcp4"]["subnet4"][0] == {"id": 5, "subnet": "10.0.0.0/24", "pools": []}


def test_set_subnet_preserve_les_reservations_existantes():
    service = _service()
    reservations = [{"hw-address": "aa:bb:cc:dd:ee:ff", "ip-address": "192.168.1.5"}]
    config = {
        "Dhcp4": {
            "subnet4": [
                {"id": 1, "subnet": "192.168.1.0/24", "pools": [], "reservations": reservations}
            ]
        }
    }
    captured: dict = {}
    with patch("subprocess.run", side_effect=_run_with_config(config, captured)):
        service.set_subnet("192.168.1.0/24", "192.168.1.50-192.168.1.99", subnet_id=1)

    written = json.loads(captured["written"])
    assert written["Dhcp4"]["subnet4"][0]["reservations"] == reservations


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


def test_mot_de_passe_lu_via_pkexec_cat():
    completed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="fromfile\n", stderr=""
    )
    with patch("subprocess.run", return_value=completed) as run:
        service = KeaService(password_file="/etc/kea/kea-api-password")

    # Lecture du secret via pkexec cat (fichier 600 root:root).
    assert run.call_args.args[0] == ["pkexec", "cat", "/etc/kea/kea-api-password"]

    captured: dict = {}

    def _capture(request, timeout):
        captured["auth"] = request.get_header("Authorization")
        return _http_response(_ok({}))

    with patch("urllib.request.urlopen", side_effect=_capture):
        service.list_leases()

    # Le mot de passe est débarrassé du saut de ligne final avant usage.
    expected = "Basic " + base64.b64encode(b"fenix:fromfile").decode("ascii")
    assert captured["auth"] == expected


def test_lecture_pkexec_echoue_aucune_authentification():
    error = subprocess.CalledProcessError(1, ["pkexec"], stderr="refusé")
    with patch("subprocess.run", side_effect=error):
        service = KeaService(password_file="/etc/kea/kea-api-password")

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


def test_restart_service_redemarre_les_deux_dans_lordre():
    service = _service()
    events: list = []

    def _run(cmd, *args, **kwargs):
        events.append(("run", cmd))
        return _completed()

    with (
        patch("subprocess.run", side_effect=_run),
        patch("time.sleep", side_effect=lambda s: events.append(("sleep", s))),
    ):
        service.restart_service()

    # DHCPv4 d'abord, attente de 2 s, puis le Control Agent.
    assert events == [
        ("run", ["pkexec", "systemctl", "restart", "kea-dhcp4-server"]),
        ("sleep", 2),
        ("run", ["pkexec", "systemctl", "restart", "kea-ctrl-agent"]),
    ]


def test_restart_service_echec_du_premier_n_atteint_pas_le_second():
    service = _service()
    error = subprocess.CalledProcessError(1, ["pkexec"], stderr="boom")
    with (
        patch("subprocess.run", side_effect=error) as run,
        patch("time.sleep") as sleep,
        pytest.raises(RuntimeError),
    ):
        service.restart_service()

    # Le serveur DHCPv4 échoue : pas d'attente, pas de redémarrage du Control Agent.
    run.assert_called_once()
    sleep.assert_not_called()
