#!/usr/bin/env python3
import argparse
import getpass
import io
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


API_URL = "https://quack.duckduckgo.com/api/email/addresses"
PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = PROJECT_DIR / ".duckmail" / "config.json"
CLEAR_SCREEN = "\033[2J\033[H"


class DuckMailError(Exception):
    pass


class Config:
    def __init__(self, path=DEFAULT_CONFIG):
        self.path = Path(path).expanduser()

    def load(self):
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.chmod(tmp_path, 0o600)
        tmp_path.replace(self.path)
        os.chmod(self.path, 0o600)


class DuckMailClient:
    def __init__(self, token, opener=urllib.request.urlopen):
        self.token = token
        self.opener = opener

    def create_address(self):
        request = urllib.request.Request(
            API_URL,
            data=b"{}",
            method="POST",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        try:
            response = self.opener(request)
            payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise DuckMailError(f"DuckDuckGo returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise DuckMailError(f"Could not reach DuckDuckGo: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise DuckMailError("DuckDuckGo returned an invalid JSON response") from exc

        address = payload.get("address")
        if not address:
            raise DuckMailError(f"DuckDuckGo response did not include an address: {payload}")
        if not address.endswith("@duck.com"):
            address = f"{address}@duck.com"
        return address


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help=f"Config path (default: {DEFAULT_CONFIG})",
    )
    parser = argparse.ArgumentParser(
        prog="duckmail",
        description="Generate DuckDuckGo Email Protection private duck.com addresses.",
        parents=[common],
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("show", parents=[common], help="Show the last generated address")
    new = subparsers.add_parser(
        "new", parents=[common], help="Generate a new private duck.com address"
    )
    new.add_argument("-l", "--label", help="Label for the generated address")

    new_with_label = subparsers.add_parser(
        "new-with-label",
        parents=[common],
        help="Generate a new address and require a label",
    )
    new_with_label.add_argument("label", help="Label for the generated address")

    subparsers.add_parser("list", parents=[common], help="List saved addresses")

    find = subparsers.add_parser("find", parents=[common], help="Search saved addresses")
    find.add_argument("query", help="Text to search for in labels and addresses")

    relabel = subparsers.add_parser(
        "relabel", parents=[common], help="Change the label for a saved address"
    )
    relabel.add_argument("target", help="Existing address or label to update")
    relabel.add_argument("label", help="New label")

    setup = subparsers.add_parser(
        "setup", parents=[common], help="Store your DuckDuckGo Email token"
    )
    setup.add_argument("--token", help="Token to store; if omitted, prompts securely")

    subparsers.add_parser("where", parents=[common], help="Show where the config file is stored")
    return parser


def save_token(config, token, stdout):
    data = config.load()
    data["token"] = token.strip()
    config.save(data)
    print(f"Token saved in {config.path}", file=stdout)
    return 0


def require_token(config_data):
    token = config_data.get("token")
    if not token:
        raise DuckMailError(
            "No token configured. Run `./duckmail.py setup` first, or pass one there."
        )
    return token


def show_last(config_data, stdout):
    address = config_data.get("last_address")
    if not address:
        print("No generated address saved yet.", file=stdout)
        print("Run: ./duckmail.py new", file=stdout)
    else:
        print("Current Duck address", file=stdout)
        print("--------------------", file=stdout)
        print(address, file=stdout)
    return 0


def now_iso():
    return datetime.now().replace(second=0, microsecond=0).strftime("%Y-%m-%d at %H:%M")


def format_created_at(value):
    if not value:
        return ""
    if " at " in value:
        return value
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone()
    return parsed.strftime("%Y-%m-%d at %H:%M")


def remember_address(data, address, label=None):
    entry = {
        "address": address,
        "label": label or "",
        "created_at": now_iso(),
    }
    addresses = data.setdefault("addresses", [])
    addresses.append(entry)
    data["last_address"] = address
    return entry


def print_addresses(entries, stdout):
    if not entries:
        print("No saved addresses yet.", file=stdout)
        print("Run: ./duckmail.py new-with-label <label>", file=stdout)
        return 0

    rows = [
        (
            entry.get("label") or "-",
            entry.get("address", ""),
            format_created_at(entry.get("created_at", "")) or "-",
        )
        for entry in entries
    ]
    label_width = max([len("LABEL")] + [len(row[0]) for row in rows])
    address_width = max([len("ADDRESS")] + [len(row[1]) for row in rows])
    created_width = max([len("CREATED")] + [len(row[2]) for row in rows])

    print("Saved Duck addresses", file=stdout)
    print("--------------------", file=stdout)
    print(
        f"{'LABEL':<{label_width}}  {'ADDRESS':<{address_width}}  {'CREATED':<{created_width}}",
        file=stdout,
    )
    print(
        f"{'-' * label_width}  {'-' * address_width}  {'-' * created_width}",
        file=stdout,
    )
    for label, address, created_at in rows:
        print(
            f"{label:<{label_width}}  {address:<{address_width}}  {created_at:<{created_width}}",
            file=stdout,
        )
    return 0


def list_addresses(config_data, stdout):
    return print_addresses(config_data.get("addresses", []), stdout)


def find_addresses(config_data, query, stdout):
    needle = query.lower()
    entries = [
        entry
        for entry in config_data.get("addresses", [])
        if needle in entry.get("label", "").lower()
        or needle in entry.get("address", "").lower()
    ]
    return print_addresses(entries, stdout)


def relabel_address(config, target, label, stdout):
    data = config.load()
    needle = target.lower()
    for entry in data.get("addresses", []):
        if (
            entry.get("address", "").lower() == needle
            or entry.get("label", "").lower() == needle
        ):
            old_label = entry.get("label") or "-"
            entry["label"] = label
            config.save(data)
            print("Updated label", file=stdout)
            print("-------------", file=stdout)
            print(f"Address: {entry.get('address', '')}", file=stdout)
            print(f"Old label: {old_label}", file=stdout)
            print(f"New label: {label}", file=stdout)
            return 0
    raise DuckMailError(f"No saved address or label matches `{target}`.")


def generate_new(config, stdout, client_factory=DuckMailClient, label=None):
    data = config.load()
    token = require_token(data)
    address = client_factory(token).create_address()
    entry = remember_address(data, address, label)
    config.save(data)
    print("New Duck address", file=stdout)
    print("----------------", file=stdout)
    print(f"Address: {address}", file=stdout)
    if label:
        print(f"Label: {label}", file=stdout)
    print(f"Created: {entry['created_at']}", file=stdout)
    return 0


def render_interactive_screen(config_data, stdout, message=None):
    last_address = config_data.get("last_address", "none")
    print(CLEAR_SCREEN, end="", file=stdout)
    print("duckmail", file=stdout)
    print("========", file=stdout)
    print(f"Current: {last_address}", file=stdout)
    print("", file=stdout)

    if message:
        print("Last result", file=stdout)
        print("-----------", file=stdout)
        print(message.rstrip(), file=stdout)
        print("", file=stdout)

    print("Actions", file=stdout)
    print("-------", file=stdout)
    print("1. New address", file=stdout)
    print("2. New address with label", file=stdout)
    print("3. List saved addresses", file=stdout)
    print("4. Find saved address", file=stdout)
    print("5. Change label", file=stdout)
    print("6. Show current address", file=stdout)
    print("7. Set token", file=stdout)
    print("q. Quit", file=stdout)


def capture_output(action):
    buffer = io.StringIO()
    action(buffer)
    return buffer.getvalue().rstrip()


def interactive(config, stdout, stdin, client_factory):
    message = None
    while True:
        data = config.load()
        render_interactive_screen(data, stdout, message)
        choice = input("Choice: ").strip().lower()

        if choice in ("q", "quit", "exit"):
            return 0
        if choice in ("6", "s", "show", ""):
            message = capture_output(lambda out: show_last(data, out))
            continue
        if choice in ("7", "t", "token", "setup"):
            token = getpass.getpass("DuckDuckGo token: ")
            message = capture_output(lambda out: save_token(config, token, out))
            continue
        if choice in ("1", "n", "new"):
            try:
                message = capture_output(
                    lambda out: generate_new(config, out, client_factory)
                )
            except DuckMailError as exc:
                message = f"Error: {exc}"
            continue
        if choice in ("2", "w", "new with label", "new-with-label"):
            label = input("Label: ").strip()
            if not label:
                message = "Label is required."
                continue
            try:
                message = capture_output(
                    lambda out: generate_new(config, out, client_factory, label)
                )
            except DuckMailError as exc:
                message = f"Error: {exc}"
            continue
        if choice in ("3", "l", "list"):
            message = capture_output(lambda out: list_addresses(data, out))
            continue
        if choice in ("4", "f", "find", "search"):
            query = input("Search: ").strip()
            message = capture_output(lambda out: find_addresses(data, query, out))
            continue
        if choice in ("5", "r", "relabel", "change label"):
            target = input("Address or current label: ").strip()
            label = input("New label: ").strip()
            if not target or not label:
                message = "Address/current label and new label are required."
                continue
            try:
                message = capture_output(
                    lambda out: relabel_address(config, target, label, out)
                )
            except DuckMailError as exc:
                message = f"Error: {exc}"
            continue
        message = "Unknown choice."


def main(argv=None, stdout=sys.stdout, stderr=sys.stderr, client_factory=DuckMailClient):
    parser = build_parser()
    args = parser.parse_args(argv)
    config = Config(args.config)

    try:
        if args.command == "setup":
            token = args.token or getpass.getpass("DuckDuckGo token: ")
            return save_token(config, token, stdout)
        if args.command == "show":
            return show_last(config.load(), stdout)
        if args.command == "new":
            return generate_new(config, stdout, client_factory, args.label)
        if args.command == "new-with-label":
            return generate_new(config, stdout, client_factory, args.label)
        if args.command == "list":
            return list_addresses(config.load(), stdout)
        if args.command == "find":
            return find_addresses(config.load(), args.query, stdout)
        if args.command == "relabel":
            return relabel_address(config, args.target, args.label, stdout)
        if args.command == "where":
            print(config.path, file=stdout)
            return 0
        return interactive(config, stdout, sys.stdin, client_factory)
    except DuckMailError as exc:
        print(f"Error: {exc}", file=stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
