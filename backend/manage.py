"""Administrative commands.

Usage (from the backend folder):
    python manage.py create-user --name "Jane Recruiter" --email jane@acme.com --role hr
    python manage.py reset-password --email jane@acme.com

Passwords are prompted for (never passed on the command line) and must meet the
same strength rules as the API.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import func

from app import models
from app.auth import ROLES, hash_password, validate_email_format, validate_password_strength
from app.db import Base, SessionLocal, engine


def _prompt_password() -> str:
    """Ask for a new password twice (hidden input) and enforce the API's strength rules."""
    password = getpass.getpass("New password: ")
    if password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")
    ok, message = validate_password_strength(password)
    if not ok:
        sys.exit(message)
    return password


def create_user(args: argparse.Namespace) -> None:
    """``create-user``: add a recruiter or candidate account (creates tables if needed)."""
    name = args.name.strip()
    if not 2 <= len(name) <= 100:
        sys.exit("Name must be between 2 and 100 characters.")
    ok, email = validate_email_format(args.email)
    if not ok:
        sys.exit(email)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.query(models.User).filter(func.lower(models.User.email) == email).first():
            sys.exit("A user with this email already exists.")
        user = models.User(name=name, email=email, password=hash_password(_prompt_password()), role=args.role)
        db.add(user)
        db.commit()
        print(f"Created {args.role} user {email} (id {user.user_id}).")


def reset_password(args: argparse.Namespace) -> None:
    """``reset-password``: set a new password, e.g. for accounts from before version 3."""
    ok, email = validate_email_format(args.email)
    if not ok:
        sys.exit(email)
    with SessionLocal() as db:
        user = db.query(models.User).filter(func.lower(models.User.email) == email).first()
        if user is None:
            sys.exit("No user with this email.")
        user.password = hash_password(_prompt_password())
        db.commit()
        print(f"Password updated for {email}.")


def main() -> None:
    """Parse the command line and run the chosen sub-command."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-user", help="Create an HR or candidate account")
    create.add_argument("--name", required=True)
    create.add_argument("--email", required=True)
    create.add_argument("--role", choices=ROLES, default="hr")
    create.set_defaults(func=create_user)
    reset = sub.add_parser("reset-password", help="Set a new password for an existing account")
    reset.add_argument("--email", required=True)
    reset.set_defaults(func=reset_password)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
