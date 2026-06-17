import csv
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from pyfarm.cli.main import cli


MINIMAL_SPEC = """
spec_version: "1.0"
kind: GrowSpec
metadata:
  name: test-oyster
  species: pleurotus.ostreatus
  substrate: coffee_grounds
  author: test@example.com
  registry: test/v1
stages:
  - name: colonisation
    duration:
      min_days: 14
      max_days: 28
    exit_condition:
      metric: visual.colonisation_pct
      threshold: ">= 0.95"
    setpoints:
      temperature:
        target: 24.0
        tolerance: 2.0
        unit: celsius
      humidity_rh:
        target: 0.90
        tolerance: 0.05
      co2_ppm:
        target: 2000
        tolerance: 500
      light:
        schedule: "0/24"
actuators:
  misting:
    kind: relay
    gpio: 17
"""

SAMPLE_CSV = "timestamp,temperature,humidity_rh,co2_ppm\n2024-01-15T08:00:00,18.2,0.93,810\n"


@pytest.fixture
def spec_file(tmp_path) -> Path:
    p = tmp_path / "test.pyfarm.yaml"
    p.write_text(MINIMAL_SPEC)
    return p


@pytest.fixture
def csv_file(tmp_path) -> Path:
    p = tmp_path / "data.csv"
    p.write_text(SAMPLE_CSV)
    return p


def test_validate_ok(spec_file):
    runner = CliRunner()
    result = runner.invoke(cli, ["grow", "validate", str(spec_file)])
    assert result.exit_code == 0
    assert "test-oyster" in result.output


def test_validate_bad_yaml(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("not: a: grow: spec")
    runner = CliRunner()
    result = runner.invoke(cli, ["grow", "validate", str(bad)])
    assert result.exit_code == 1


def test_replay_runs(spec_file, csv_file):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["grow", "replay", str(spec_file), str(csv_file)],
    )
    assert result.exit_code == 0, result.output
    assert "Replay complete" in result.output


def test_start_command_runs_then_stops(spec_file):
    """Verify start builds actuators and enters the control loop (mocked to exit immediately)."""
    runner = CliRunner()

    # Patch ControlRunner.run to return immediately so the test doesn't spin forever.
    async def _instant_run(self):
        self.stop()

    with patch("pyfarm.control.engine.runner.ControlRunner.run", _instant_run):
        result = runner.invoke(cli, ["grow", "start", str(spec_file)])

    assert result.exit_code == 0, result.output
    assert "test-oyster" in result.output
    assert "Starting control loop" in result.output
