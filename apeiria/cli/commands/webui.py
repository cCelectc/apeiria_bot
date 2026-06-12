from __future__ import annotations

import asyncio

import click

from apeiria.cli.i18n import _


async def _run_with_engine(coro_factory):  # noqa: ANN001
    from apeiria.db.engine import close_engine, init_engine
    from apeiria.db.runtime import database_runtime

    database_runtime.ensure_ready()
    await init_engine(database_runtime.database_path())
    try:
        return await coro_factory()
    finally:
        await close_engine()


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    help=_("Manage Web UI accounts and recovery."),
)
def webui() -> None:
    """Manage Web UI accounts and recovery."""


@webui.group("accounts", help=_("Manage Web UI accounts from the host."))
def accounts() -> None:
    """Manage Web UI accounts from the host."""


@accounts.command(
    "recover",
    help=_("Create or recover one owner account from the host."),
)
@click.option(
    "--username",
    prompt=True,
    help=_("Owner username to create or recover."),
)
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help=_("New password for the owner account."),
)
def recover(*, username: str, password: str) -> None:
    """Create or recover one owner account with a host-only password reset."""
    try:

        async def _op():
            from apeiria.app.access.webui_auth.secrets import recover_owner_account

            return await recover_owner_account(username, password)

        normalized_username, created = asyncio.run(_run_with_engine(_op))
    except ValueError as exc:
        if str(exc) == "username_invalid":
            raise click.ClickException(_("username is required")) from None
        if str(exc) == "password_invalid":
            raise click.ClickException(_("password must be 8-128 characters")) from None
        raise click.ClickException(str(exc)) from exc

    if created:
        click.echo(
            _("created owner account: {username}").format(username=normalized_username)
        )
        return

    click.echo(
        _("recovered owner account: {username}").format(username=normalized_username)
    )


webui.add_command(recover)


@accounts.command("list", help=_("List Web UI accounts."))
def list_accounts_command() -> None:
    """List Web UI accounts from the host."""

    async def _op():
        from apeiria.app.access.webui_auth.secrets import list_accounts

        return await list_accounts()

    items = asyncio.run(_run_with_engine(_op))
    if not items:
        click.echo(_("no webui accounts"))
        return
    for item in items:
        status = _("disabled") if item.is_disabled else _("enabled")
        click.echo(
            _(
                "account: {username} status={status} "
                "last_login={last_login} password_changed={password_changed}"
            ).format(
                username=item.username,
                status=status,
                last_login=item.last_login_at or "-",
                password_changed=item.password_changed_at or "-",
            )
        )
