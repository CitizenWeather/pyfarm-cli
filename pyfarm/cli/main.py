import click

from .cultivars import cultivars
from .grow import grow
from .protocols import protocols


@click.group()
def cli():
    """pyfarm — mushroom fruiting chamber automation."""
    pass


cli.add_command(grow)
cli.add_command(cultivars)
cli.add_command(protocols)
