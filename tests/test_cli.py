"""CLI smoke tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from pyfarm.cli.grow import grow


RUNNER = CliRunner()


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

def test_validate_missing_file():
    result = RUNNER.invoke(grow, ["validate", "/nonexistent/path.yaml"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# events
# ---------------------------------------------------------------------------

def _mock_events_response(data):
    resp = MagicMock()
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    return resp


def test_events_prints_events():
    sample = [
        {"timestamp": "2024-01-01T00:00:00+00:00", "kind": "actuator", "message": "fan -> ON"},
        {"timestamp": "2024-01-01T00:00:05+00:00", "kind": "alert_fired", "message": "too hot"},
    ]
    with patch("httpx.get", return_value=_mock_events_response(sample)):
        result = RUNNER.invoke(grow, ["events", "--port", "8765"])
    assert result.exit_code == 0
    assert "fan -> ON" in result.output
    assert "too hot" in result.output


def test_events_empty_response():
    with patch("httpx.get", return_value=_mock_events_response([])):
        result = RUNNER.invoke(grow, ["events"])
    assert result.exit_code == 0
    assert result.output.strip() == ""


# ---------------------------------------------------------------------------
# actuators
# ---------------------------------------------------------------------------

def _mock_actuators_response(data):
    resp = MagicMock()
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    return resp


def test_actuators_shows_states():
    sample = {
        "fan": {"on": True, "command": True, "last_changed": "2024-01-01T00:00:00+00:00", "seconds_in_state": 90.0},
        "heater": {"on": False, "command": False, "last_changed": "2024-01-01T00:00:00+00:00", "seconds_in_state": 300.0},
    }
    with patch("httpx.get", return_value=_mock_actuators_response(sample)):
        result = RUNNER.invoke(grow, ["actuators"])
    assert result.exit_code == 0
    assert "fan" in result.output
    assert "ON" in result.output
    assert "heater" in result.output
    assert "OFF" in result.output


def test_actuators_no_actuators():
    with patch("httpx.get", return_value=_mock_actuators_response({})):
        result = RUNNER.invoke(grow, ["actuators"])
    assert result.exit_code == 0
    assert "No actuators registered" in result.output
