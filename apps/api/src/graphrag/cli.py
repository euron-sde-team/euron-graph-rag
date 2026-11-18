"""Operator command line.

graphrag migrate
graphrag user create --email you@example.com --name "You" --admin
graphrag demo seed
graphrag graph rebuild --project port-intelligence
graphrag openapi --out docs/api/openapi.json
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from graphrag.core.config import get_settings
from graphrag.core.logging import configure_logging

app = typer.Typer(
    no_args_is_help=True, help="Euron GraphRAG server command line.", add_completion=False
)
user_app = typer.Typer(no_args_is_help=True, help="Manage accounts.")
demo_app = typer.Typer(no_args_is_help=True, help="Demo data for local stacks.")
graph_app = typer.Typer(no_args_is_help=True, help="Operate on a project's knowledge graph.")
app.add_typer(user_app, name="user")
app.add_typer(demo_app, name="demo")
app.add_typer(graph_app, name="graph")


@app.callback()
def _setup() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, "console")


@app.command()
def migrate() -> None:
    """Apply pending database migrations."""
    from graphrag.db.migrate import migrate as run

    asyncio.run(run(get_settings()))
    typer.echo("migrations applied")


@user_app.command("create")
def create_user(
    email: Annotated[str, typer.Option(help="Sign-in email.")],
    name: Annotated[str, typer.Option(help="Display name.")],
    password: Annotated[
        str | None,
        typer.Option(
            envvar="GRAPHRAG_USER_PASSWORD",
            help="Password. Without it the CLI prompts on a terminal, reads one line from "
            "standard input (CI), or, with neither (an ECS one-off task), generates a "
            "temporary password and prints it once.",
        ),
    ] = None,
    admin: Annotated[bool, typer.Option(help="Instance administrator.")] = False,
) -> None:
    """Create an account."""
    from graphrag.db.session import Database
    from graphrag.services.users import create_user as create

    secret, generated = resolve_password(password)

    async def run() -> None:
        db = Database(get_settings())
        try:
            async with db.session() as session:
                user = await create(
                    session, email=email, name=name, password=secret, is_admin=admin
                )
                typer.echo(f"created {user.email} ({user.id})")
        finally:
            await db.dispose()

    asyncio.run(run())
    if generated:
        typer.echo(f"temporary password: {secret}")
        typer.echo("Sign in and change it at once: account menu, Change password.")


def resolve_password(given: str | None) -> tuple[str, bool]:
    """The password to set, and whether it was generated.

    A given password wins. Otherwise prompt on a terminal, or take the first line of standard
    input; with nobody to ask (an ECS one-off task has neither) generate a temporary one, so
    the command still works there.
    """
    from graphrag.core.security import temporary_password

    if given:
        return given, False
    if sys.stdin.isatty():
        entered: str = typer.prompt("Password", hide_input=True, confirmation_prompt=True)
        return entered, False
    line = sys.stdin.readline().rstrip("\n")
    if line:
        return line, False
    return temporary_password(), True


@demo_app.command("seed")
def seed(
    password: Annotated[
        str | None, typer.Option(envvar="DEMO_PASSWORD", help="Password for every demo account.")
    ] = None,
    traffic: Annotated[bool, typer.Option(help="Replay two weeks of demo questions.")] = True,
) -> None:
    """Demo accounts, a project with fourteen notes, its knowledge graph and a question history."""
    from graphrag.demo.seed import run

    settings = get_settings()
    if settings.is_production:
        raise typer.BadParameter("refusing to seed demo data with APP_ENV=production")
    secret = password or (
        settings.demo_password.get_secret_value() if settings.demo_password else None
    )
    if not secret:
        raise typer.BadParameter("set DEMO_PASSWORD (make env generates one)")
    asyncio.run(run(settings, secret, traffic=traffic))


@graph_app.command("rebuild")
def rebuild_graph(
    project: Annotated[str, typer.Option(help="Project slug.")],
) -> None:
    """Queue a build: resolve duplicates, detect communities and rewrite the reports."""
    from graphrag.demo.seed import rebuild

    if not asyncio.run(rebuild(get_settings(), project)):
        raise typer.BadParameter(f"no project with the slug '{project}'")
    typer.echo("build queued")


@app.command()
def openapi(
    out: Annotated[Path, typer.Option(help="Where to write the OpenAPI document.")] = Path(
        "openapi.json"
    ),
) -> None:
    """Export the OpenAPI document generated from the routes."""
    from graphrag.main import create_app

    schema = create_app().openapi()
    out.write_text(json.dumps(schema, indent=2, sort_keys=False) + "\n")
    typer.echo(f"wrote {out}")


if __name__ == "__main__":
    app()
