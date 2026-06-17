import csv
from pathlib import Path

import pytest
from click.testing import CliRunner

from pyfarm.cli.main import cli


MINIMAL_SPEC = """
spec_version: "1.0"
kind: GrowSpec
metadata:
  name: test-oyster
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
      humidity_rh:
        target: 0.90
        tolerance: 0.05
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
    assert result.exit_code == 0
    assert "Replay complete" in result.output
