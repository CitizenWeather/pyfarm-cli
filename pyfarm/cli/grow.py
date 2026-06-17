from __future__ import annotations

import asyncio
from pathlib import Path

import click


@click.group()
def grow():
    """Manage grow runs."""
    pass


@grow.command("validate")
@click.argument("spec_path", type=click.Path(exists=True, path_type=Path))
def validate(spec_path: Path) -> None:
    """Validate a GrowSpec YAML file without starting a run."""
    from pyfarm.control.spec.loader import load_spec, SpecLoadError

    try:
        spec = load_spec(spec_path)
    except SpecLoadError as e:
        click.echo(f"✗ {e}", err=True)
        raise SystemExit(1)

    stage_names = ", ".join(s.name for s in spec.stages)
    click.echo(f"✓ {spec.metadata.name} ({len(spec.stages)} stages: {stage_names})")


@grow.command("start")
@click.argument("spec_path", type=click.Path(exists=True, path_type=Path))
@click.option("--chamber", default=None, help="Chamber identifier (future: loads sensor config)")
@click.option("--tick", default=10, show_default=True, help="Control loop interval in seconds")
def start(spec_path: Path, chamber: str | None, tick: int) -> None:
    """Start a grow run from a GrowSpec YAML file."""
    from pyfarm.control.spec.loader import load_spec, SpecLoadError
    from pyfarm.control.actuators.logging_actuator import LoggingActuator
    from pyfarm.control.engine.runner import ControlRunner

    try:
        spec = load_spec(spec_path)
    except SpecLoadError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    click.echo(f"Spec:    {spec.metadata.name}")
    click.echo(f"Stages:  {', '.join(s.name for s in spec.stages)}")
    if chamber:
        click.echo(f"Chamber: {chamber}")
    click.echo(f"Tick:    {tick}s")
    click.echo("Starting control loop (Ctrl+C to stop)...\n")

    actuators = {name: LoggingActuator(name) for name in spec.actuators}
    runner = ControlRunner(spec=spec, sensors=[], actuators=actuators, tick_seconds=tick)

    try:
        asyncio.run(runner.run())
    except KeyboardInterrupt:
        runner.stop()
        click.echo("\nStopped.")


@grow.command("replay")
@click.argument("spec_path", type=click.Path(exists=True, path_type=Path))
@click.argument("sensor_csv", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--metrics",
    default="temperature,humidity_rh,co2_ppm",
    show_default=True,
    help="Comma-separated list of metrics to read from the CSV",
)
def replay(spec_path: Path, sensor_csv: Path, metrics: str) -> None:
    """Replay a grow run against pre-recorded sensor data (CSV).

    The CSV must have a 'timestamp' column and one column per metric.
    """
    from pyfarm.control.replay.scenario import run_scenario

    metric_list = [m.strip() for m in metrics.split(",")]
    click.echo(f"Spec:    {spec_path.name}")
    click.echo(f"Data:    {sensor_csv.name}  ({', '.join(metric_list)})")
    click.echo()

    runner = asyncio.run(run_scenario(spec_path, sensor_csv, metrics=metric_list))

    total = sum(len(a.log) for a in runner.actuators.values())
    click.echo(f"\nReplay complete. {total} actuator state change(s) logged.")
    for name, actuator in runner.actuators.items():
        click.echo(f"  {name}: {len(actuator.log)} transition(s)")


@grow.command("status")
@click.argument("chamber", default="default")
def status(chamber: str) -> None:
    """Show live status of a running grow (requires local API)."""
    # Stub: will query the local FastAPI instance once the API layer is built
    click.echo(f"Chamber: {chamber}")
    click.echo("Status API not yet implemented. Start a run with 'pyfarm grow start'.")
