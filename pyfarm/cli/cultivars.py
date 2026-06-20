"""Cultivar registry commands."""

from __future__ import annotations

import asyncio

import click


@click.group()
def cultivars():
    """Manage crop cultivars."""
    pass


@cultivars.command("list")
@click.option(
    "--crop",
    type=click.Choice(["mushroom", "microgreen"]),
    default=None,
    help="Filter by crop type",
)
def list_cultivars(crop: str | None) -> None:
    """List available cultivars."""
    from pyfarm.crops import MemoryRegistry, CropType

    async def run():
        registry = MemoryRegistry()
        crop_type = CropType[crop.upper()] if crop else None
        cultivars = await registry.list_cultivars(crop_type=crop_type)

        if not cultivars:
            click.echo("No cultivars found.")
            return

        # Group by crop type
        by_type = {}
        for c in cultivars:
            crop = c.crop_type.value
            if crop not in by_type:
                by_type[crop] = []
            by_type[crop].append(c)

        for crop_name in sorted(by_type.keys()):
            click.echo(f"\n{crop_name.capitalize()}:")
            for c in by_type[crop_name]:
                click.echo(f"  {c.id:30s} {c.name:30s} ({c.cycle_days}d, {c.yield_g_per_m2:.0f}g/m²)")

    asyncio.run(run())


@cultivars.command("show")
@click.argument("cultivar_id")
def show_cultivar(cultivar_id: str) -> None:
    """Show details of a specific cultivar."""
    from pyfarm.crops import MemoryRegistry

    async def run():
        registry = MemoryRegistry()
        cultivar = await registry.get_cultivar(cultivar_id)

        if not cultivar:
            click.echo(f"Cultivar not found: {cultivar_id}", err=True)
            raise SystemExit(1)

        click.echo(f"Name:      {cultivar.name}")
        click.echo(f"Species:   {cultivar.species}")
        click.echo(f"Type:      {cultivar.crop_type.value}")
        click.echo(f"Source:    {cultivar.source}")
        click.echo(f"Cycle:     {cultivar.cycle_days} days")
        click.echo(f"Yield:     {cultivar.yield_g_per_m2} g/m²")
        click.echo(f"Temp:      {cultivar.optimal_temperature.min}-{cultivar.optimal_temperature.max}°C")
        click.echo(f"Humidity:  {cultivar.optimal_humidity.min}-{cultivar.optimal_humidity.max}%")

        if cultivar.optimal_ec:
            click.echo(f"EC:        {cultivar.optimal_ec.min}-{cultivar.optimal_ec.max} mS/cm")
        if cultivar.optimal_ph:
            click.echo(f"pH:        {cultivar.optimal_ph.min}-{cultivar.optimal_ph.max}")
        if cultivar.optimal_light_dli:
            click.echo(f"DLI:       {cultivar.optimal_light_dli} mol/m²/day")

        click.echo(f"\nPhenophases:")
        for i, phase in enumerate(cultivar.phenophases):
            click.echo(
                f"  {i+1}. {phase.stage:15s} {phase.duration_days:3d}d | "
                f"T: {phase.temperature.min:.0f}-{phase.temperature.max:.0f}°C | "
                f"H: {phase.humidity.min:.0f}-{phase.humidity.max:.0f}%"
            )
            if phase.light_dli:
                click.echo(f"        DLI: {phase.light_dli} mol/m²/day")

    asyncio.run(run())
