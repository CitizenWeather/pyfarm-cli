from __future__ import annotations

import asyncio
import time
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


@grow.command("events")
@click.option("--port", default=8765, show_default=True, help="Port the control API is listening on")
@click.option("--since", default=None, help="ISO-8601 timestamp; show only events after this time")
@click.option("--follow", is_flag=True, help="Poll continuously and stream new events (Ctrl-C to stop)")
@click.option("--interval", default=2.0, show_default=True, help="Poll interval in seconds (--follow mode)")
def events(port: int, since: str | None, follow: bool, interval: float) -> None:
    """Stream control events from a running grow.

    Without --follow, prints all events (optionally filtered by --since) and
    exits.  With --follow, polls the API every --interval seconds and prints
    new events as they arrive until interrupted.
    """
    import httpx

    base_url = f"http://127.0.0.1:{port}/events"

    def _fetch(after: str | None = None) -> list[dict]:
        params = {"since": after} if after else {}
        try:
            resp = httpx.get(base_url, params=params, timeout=5.0)
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            click.echo(
                f"Could not connect to API at {base_url}. Is a run active? "
                f"(use 'pyfarm grow start --api-port {port}')",
                err=True,
            )
            raise SystemExit(1)
        except httpx.HTTPStatusError as e:
            click.echo(f"API error: {e}", err=True)
            raise SystemExit(1)

    def _print_event(ev: dict) -> None:
        click.echo(f"[{ev['timestamp']}] {ev['kind']}: {ev['message']}")

    batch = _fetch(since)
    for ev in batch:
        _print_event(ev)

    if not follow:
        return

    last_ts = batch[-1]["timestamp"] if batch else since
    try:
        while True:
            time.sleep(interval)
            new_events = _fetch(last_ts)
            for ev in new_events:
                _print_event(ev)
            if new_events:
                last_ts = new_events[-1]["timestamp"]
    except KeyboardInterrupt:
        pass


@grow.command("actuators")
@click.option("--port", default=8765, show_default=True, help="Port the control API is listening on")
def actuators(port: int) -> None:
    """Show current actuator states from a running grow."""
    import httpx

    url = f"http://127.0.0.1:{port}/actuators"
    try:
        resp = httpx.get(url, timeout=5.0)
        resp.raise_for_status()
    except httpx.ConnectError:
        click.echo(
            f"Could not connect to API at {url}. Is a run active? "
            f"(use 'pyfarm grow start --api-port {port}')",
            err=True,
        )
        raise SystemExit(1)
    except httpx.HTTPStatusError as e:
        click.echo(f"API error: {e}", err=True)
        raise SystemExit(1)

    data = resp.json()
    if not data:
        click.echo("No actuators registered.")
        return

    click.echo("Actuators:")
    for name, state in data.items():
        on_str = "ON " if state["on"] else "OFF"
        secs = state.get("seconds_in_state", 0)
        mins, s = divmod(int(secs), 60)
        hrs, m = divmod(mins, 60)
        duration = f"{hrs}h {m:02d}m {s:02d}s" if hrs else f"{m}m {s:02d}s"
        click.echo(f"  {name}: {on_str}  ({duration} in this state)")
