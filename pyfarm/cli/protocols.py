"""Protocol library commands."""

from __future__ import annotations

from pathlib import Path

import click


@click.group()
def protocols():
    """Manage GrowSpec protocols."""
    pass


@protocols.command("list")
@click.option(
    "--crop",
    type=click.Choice(["mushroom", "microgreen"]),
    default=None,
    help="Filter by crop type",
)
def list_protocols(crop: str | None) -> None:
    """List available protocols."""
    from pyfarm.protocols.loader import ProtocolLoader

    loader = ProtocolLoader()
    protocols_list = loader.list_protocols()

    if not protocols_list:
        click.echo("No protocols found.")
        return

    # Filter if needed
    if crop:
        filtered = [p for p in protocols_list if crop.lower() in p.get("id", "").lower()]
        if not filtered:
            click.echo(f"No {crop} protocols found.")
            return
        protocols_list = filtered

    click.echo("Available protocols:\n")
    for p in protocols_list:
        difficulty = p.get("difficulty", "unknown")
        cycle = p.get("cycle_days", 0)
        click.echo(f"  {p['cultivar_id']:25s} {p['name']:35s} {difficulty:12s} ({cycle}d)")


@protocols.command("show")
@click.argument("protocol_path", type=click.Path(exists=True, path_type=Path))
def show_protocol(protocol_path: Path) -> None:
    """Show details of a protocol."""
    from pyfarm.protocols.loader import ProtocolLoader

    loader = ProtocolLoader()

    try:
        spec = loader.load_spec(protocol_path)
    except Exception as e:
        click.echo(f"Error loading protocol: {e}", err=True)
        raise SystemExit(1)

    valid, errors = loader.validate_spec(spec)

    click.echo(f"Name:       {spec.get('name', 'N/A')}")
    click.echo(f"Cultivar:   {spec.get('cultivar_id', 'N/A')}")
    click.echo(f"Author:     {spec.get('author', 'N/A')}")
    click.echo(f"Cycle:      {spec.get('cycle_days', 0)} days")
    click.echo(f"Difficulty: {spec.get('difficulty', 'N/A')}")
    click.echo(f"Expected:   {spec.get('expected_yield_g_per_m2', 0)} g/m²")

    if not valid:
        click.echo("\nValidation errors:", err=True)
        for err in errors:
            click.echo(f"  - {err}", err=True)
        raise SystemExit(1)

    click.echo(f"\nPhases ({len(spec.get('phases', []))}):")
    for i, phase in enumerate(spec.get("phases", [])):
        name = phase.get("name", f"Phase {i+1}")
        days = phase.get("duration_days", 0)
        temp = phase.get("temperature", {})
        click.echo(f"  {i+1}. {name:15s} {days:3d}d | T: {temp.get('min', 0):.0f}-{temp.get('max', 0):.0f}°C")

    tags = spec.get("tags", [])
    if tags:
        click.echo(f"\nTags: {', '.join(tags)}")


@protocols.command("validate")
@click.argument("protocol_path", type=click.Path(exists=True, path_type=Path))
def validate_protocol(protocol_path: Path) -> None:
    """Validate a protocol specification."""
    from pyfarm.protocols.loader import ProtocolLoader

    loader = ProtocolLoader()

    try:
        spec = loader.load_spec(protocol_path)
    except Exception as e:
        click.echo(f"✗ Error loading: {e}", err=True)
        raise SystemExit(1)

    valid, errors = loader.validate_spec(spec)

    if valid:
        click.echo(f"✓ Valid: {spec.get('name', 'Protocol')}")
    else:
        click.echo(f"✗ Invalid: {spec.get('name', 'Protocol')}")
        for err in errors:
            click.echo(f"    {err}", err=True)
        raise SystemExit(1)
