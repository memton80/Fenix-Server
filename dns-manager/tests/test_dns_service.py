"""Tests pour services.dns_service — subprocess (pkexec) mocké."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest
from models.dns_record import DnsRecord
from models.dns_zone import DnsZone
from services.dns_service import DnsService

_ZONELIST = """
  2 zone(s)
  pszZoneName                 : example.lan
  pszZoneName                 : 1.168.192.in-addr.arpa
"""

_QUERY = """
  Name=, Records=1, Children=0
    A: 192.168.1.10 (flags=600000f0, serial=110, ttl=900)
  Name=web, Records=1, Children=0
    A: 192.168.1.20 (flags=f0, serial=110, ttl=900)
  Name=alias, Records=1, Children=0
    CNAME: web.example.lan (flags=f0, serial=110, ttl=900)
"""


def _completed(stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def test_list_zones_parse_zonelist():
    service = DnsService()
    with patch("subprocess.run", return_value=_completed(_ZONELIST)) as run:
        zones = service.list_zones()
    assert zones == [
        DnsZone("example.lan", reverse=False),
        DnsZone("1.168.192.in-addr.arpa", reverse=True),
    ]
    assert run.call_args.args[0] == ["pkexec", "samba-tool", "dns", "zonelist", "127.0.0.1"]


def test_list_records_parse_query():
    service = DnsService()
    with patch("subprocess.run", return_value=_completed(_QUERY)):
        records = service.list_records("example.lan")
    assert records == [
        DnsRecord("@", "A", "192.168.1.10", "example.lan"),
        DnsRecord("web", "A", "192.168.1.20", "example.lan"),
        DnsRecord("alias", "CNAME", "web.example.lan", "example.lan"),
    ]


def test_add_record_via_samba_tool():
    service = DnsService()
    with patch("subprocess.run", return_value=_completed()) as run:
        record = service.add_record("example.lan", "web", "A", "192.168.1.20")
    assert record == DnsRecord("web", "A", "192.168.1.20", "example.lan")
    assert run.call_args.args[0] == [
        "pkexec",
        "samba-tool",
        "dns",
        "add",
        "127.0.0.1",
        "example.lan",
        "web",
        "A",
        "192.168.1.20",
    ]


def test_delete_record_via_samba_tool():
    service = DnsService()
    with patch("subprocess.run", return_value=_completed()) as run:
        service.delete_record("example.lan", "web", "A", "192.168.1.20")
    assert run.call_args.args[0][:4] == ["pkexec", "samba-tool", "dns", "delete"]


def test_run_samba_dns_echec_leve_runtimeerror():
    service = DnsService()
    error = subprocess.CalledProcessError(1, ["pkexec"], stderr="boom")
    with patch("subprocess.run", side_effect=error), pytest.raises(RuntimeError):
        service.list_zones()
