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
    from pyfarm.control.spec.loader import load_spec, SpecValidationError

    try:
        spec = load_spec(spec_path)
    except SpecValidationError as e:
        click.echo(f"✗ {e}", err=True)
        raise SystemExit(1)

    stage_names = ", ".join(s.name for s in spec.stages)
    click.echo(f"✓ {spec.metadata.name} ({len(spec.stages)} stages: {stage_names})")


@grow.command("start")
@click.argument("spec_path", type=click.Path(exists=True, path_type=Path))
@click.option("--chamber", default=None, help="Chamber identifier (future: loads sensor config)")
@click.option("--tick", default=10, show_default=True, help="Control loop interval in seconds")
@click.option("--api-port", default=None, type=int, help="Expose live status API on this port")
def start(spec_path: Path, chamber: str | None, tick: int, api_port: int | None) -> None:
    """Start a grow run from a GrowSpec YAML file."""
    from pyfarm.control.spec.loader import load_spec, SpecValidationError
    from pyfarm.control.extensions import build_actuator, build_notifiers, build_alert_evaluator
    from pyfarm.control.engine.runner import ControlRunner

    try:
        spec = load_spec(spec_path)
    except SpecValidationError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    click.echo(f"Spec:    {spec.metadata.name}")
    click.echo(f"Stages:  {', '.join(s.name for s in spec.stages)}")
    if chamber:
        click.echo(f"Chamber: {chamber}")
    click.echo(f"Tick:    {tick}s")
    if api_port:
        click.echo(f"API:     http://127.0.0.1:{api_port}/status")

    try:
        actuators = {
            name: build_actuator(name, actuator_spec)
            for name, actuator_spec in spec.actuators.items()
        }
    except ValueError as e:
        click.echo(f"Error building actuators: {e}", err=True)
        raise SystemExit(1)

    channels = build_notifiers(spec.notifications)
    alert_evaluator = build_alert_evaluator(channels, spec)
    if channels:
        click.echo(f"Notify:  {', '.join(channels)}")
    click.echo("Starting control loop (Ctrl+C to stop)...\n")

    runner = ControlRunner(
        spec=spec,
        sensors=[],
        actuators=actuators,
        alert_evaluator=alert_evaluator,
        tick_seconds=tick,
        api_port=api_port,
    )

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

    total = sum(len(a.history) for a in runner.actuators.values())
    click.echo(f"\nReplay complete. {total} actuator state change(s) logged.")
    for name, actuator in runner.actuators.items():
        click.echo(f"  {name}: {len(actuator.history)} transition(s)")


@grow.command("status")
@click.option("--port", default=8765, show_default=True, help="Port the control API is listening on")
def status(port: int) -> None:
    """Show live status of a running grow."""
    import httpx

    url = f"http://127.0.0.1:{port}/status"
    try:
        resp = httpx.get(url, timeout=5.0)
        resp.raise_for_status()
    except httpx.ConnectError:
        click.echo(f"Could not connect to API at {url}. Is a run active? (use 'pyfarm grow start --api-port {port}')", err=True)
        raise SystemExit(1)
    except httpx.HTTPStatusError as e:
        click.echo(f"API error: {e}", err=True)
        raise SystemExit(1)

    import json
    data = resp.json()
    click.echo(f"Run:     {data['run_id']}")
    click.echo(f"Spec:    {data['spec_name']}")
    click.echo(f"Stage:   {data['current_stage']} ({data['elapsed_days']:.2f} days)")
    if data["readings"]:
        click.echo("Sensors:")
        for m, r in data["readings"].items():
            stale = " [STALE]" if r["stale"] else ""
            click.echo(f"  {m}: {r['value']} {r['unit']}{stale}")
    if data["derived"]:
        click.echo("Derived:")
        for k, v in data["derived"].items():
            click.echo(f"  {k}: {v:.3f}")
    if data["recent_events"]:
        click.echo("Recent events:")
        for ev in data["recent_events"][-5:]:
            click.echo(f"  [{ev['kind']}] {ev['message']}")
