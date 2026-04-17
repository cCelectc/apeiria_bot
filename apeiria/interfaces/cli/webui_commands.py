from __future__ import annotations

import click

from apeiria.infra.webui_auth.secrets import (
    create_account,
    create_registration_code,
    delete_account,
    list_accounts,
    list_registration_codes,
    recover_owner_account,
    revoke_registration_code,
    set_account_disabled,
    set_account_password,
)

from .i18n import _


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    help=_("Manage Web UI accounts and recovery."),
)
def webui() -> None:
    """Manage Web UI accounts and recovery."""


@webui.group("accounts", help=_("Manage Web UI accounts from the host."))
def accounts() -> None:
    """Manage Web UI accounts from the host."""


@webui.group("codes", help=_("Manage Web UI registration codes from the host."))
def codes() -> None:
    """Manage Web UI registration codes from the host."""


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
        normalized_username, created = recover_owner_account(username, password)
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
    items = list_accounts()
    if not items:
        click.echo(_("no webui accounts"))
        return
    for item in items:
        status = _("disabled") if item.is_disabled else _("enabled")
        click.echo(
            _(
                "account: {username} role={role} status={status} "
                "last_login={last_login} password_changed={password_changed}"
            ).format(
                username=item.username,
                role=item.role,
                status=status,
                last_login=item.last_login_at or "-",
                password_changed=item.password_changed_at or "-",
            )
        )


@accounts.command("create", help=_("Create one Web UI account from the host."))
@click.option("--username", prompt=True, help=_("Account username."))
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help=_("Account password."),
)
def create(*, username: str, password: str) -> None:
    """Create one Web UI account from the host."""
    try:
        normalized_username = create_account(username, password)
    except ValueError as exc:
        code = str(exc)
        if code == "username_invalid":
            raise click.ClickException(_("username is required")) from None
        if code == "username_taken":
            raise click.ClickException(_("username already exists")) from None
        if code == "password_invalid":
            raise click.ClickException(_("password must be 8-128 characters")) from None
        raise click.ClickException(code) from exc
    click.echo(_("created account: {username}").format(username=normalized_username))


@accounts.command("passwd", help=_("Reset one Web UI account password from the host."))
@click.option("--username", prompt=True, help=_("Account username."))
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help=_("Account password."),
)
def passwd(*, username: str, password: str) -> None:
    """Reset one Web UI account password from the host."""
    try:
        normalized_username = set_account_password(username, password)
    except ValueError as exc:
        if str(exc) == "account_not_found":
            raise click.ClickException(_("account not found")) from None
        if str(exc) == "password_invalid":
            raise click.ClickException(_("password must be 8-128 characters")) from None
        raise click.ClickException(str(exc)) from exc
    click.echo(_("updated password: {username}").format(username=normalized_username))


@accounts.command("disable", help=_("Disable one Web UI account from the host."))
@click.option("--username", prompt=True, help=_("Account username."))
def disable(*, username: str) -> None:
    """Disable one Web UI account from the host."""
    try:
        normalized_username = set_account_disabled(username, disabled=True)
    except ValueError as exc:
        code = str(exc)
        if code == "account_not_found":
            raise click.ClickException(_("account not found")) from None
        if code == "last_owner_forbidden":
            raise click.ClickException(_("cannot remove last enabled owner")) from None
        raise click.ClickException(code) from exc
    click.echo(_("disabled account: {username}").format(username=normalized_username))


@accounts.command("enable", help=_("Enable one Web UI account from the host."))
@click.option("--username", prompt=True, help=_("Account username."))
def enable(*, username: str) -> None:
    """Enable one Web UI account from the host."""
    try:
        normalized_username = set_account_disabled(username, disabled=False)
    except ValueError as exc:
        if str(exc) == "account_not_found":
            raise click.ClickException(_("account not found")) from None
        raise click.ClickException(str(exc)) from exc
    click.echo(_("enabled account: {username}").format(username=normalized_username))


@accounts.command("delete", help=_("Delete one Web UI account from the host."))
@click.option("--username", prompt=True, help=_("Account username."))
def delete(*, username: str) -> None:
    """Delete one Web UI account from the host."""
    try:
        normalized_username = delete_account(username)
    except ValueError as exc:
        code = str(exc)
        if code == "account_not_found":
            raise click.ClickException(_("account not found")) from None
        if code == "last_owner_forbidden":
            raise click.ClickException(_("cannot remove last enabled owner")) from None
        raise click.ClickException(code) from exc
    click.echo(_("deleted account: {username}").format(username=normalized_username))


@codes.command("list", help=_("List Web UI registration codes."))
def list_codes_command() -> None:
    """List Web UI registration codes from the host."""
    items = list_registration_codes()
    if not items:
        click.echo(_("no registration codes"))
        return
    for item in items:
        click.echo(
            _(
                "code: {code} role={role} created_by={created_by} "
                "created_at={created_at}"
            ).format(
                code=item.code,
                role=item.role,
                created_by=item.created_by,
                created_at=item.created_at,
            )
        )


@codes.command("create", help=_("Create one Web UI registration code from the host."))
@click.option("--role", default="owner", show_default=True, help=_("Account role."))
def create_code(*, role: str) -> None:
    """Create one Web UI registration code from the host."""
    try:
        item = create_registration_code(role=role)
    except ValueError as exc:
        if str(exc) == "invalid_role":
            raise click.ClickException(_("invalid role")) from None
        raise click.ClickException(str(exc)) from exc
    click.echo(_("created registration code: {code}").format(code=item.code))


@codes.command("revoke", help=_("Revoke one Web UI registration code from the host."))
@click.option("--code", prompt=True, help=_("Registration code."))
def revoke(*, code: str) -> None:
    """Revoke one Web UI registration code from the host."""
    try:
        normalized_code = revoke_registration_code(code)
    except ValueError as exc:
        if str(exc) == "registration_code_not_found":
            raise click.ClickException(_("registration code not found")) from None
        raise click.ClickException(str(exc)) from exc
    click.echo(_("revoked registration code: {code}").format(code=normalized_code))
