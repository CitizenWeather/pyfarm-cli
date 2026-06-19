import click
from .grow import grow


@click.group()
def cli():
    """pyfarm — mushroom fruiting chamber automation."""
    pass


cli.add_command(grow)
