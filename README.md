# duckmail

Small terminal helper for DuckDuckGo Email Protection private addresses.

DuckDuckGo documents generating Private Duck Addresses through their apps,
browser extensions, and Email Protection settings. This tool uses the same
network endpoint that those clients use:

```text
POST https://quack.duckduckgo.com/api/email/addresses
Authorization: Bearer <token>
```

That endpoint is not a formally documented public API, so it can change.

## Setup

1. Open `https://duckduckgo.com/email/` once in a logged-in browser.
2. Open browser developer tools, then the Network tab.
3. Generate a Private Duck Address.
4. Find the `addresses` request and copy the value after
   `Authorization: Bearer`.
5. Store it locally:

```sh
./duckmail.py setup
```

The token is stored in the project folder at `.duckmail/config.json` with file
mode `0600`.
Treat the token like a password.

## Usage

On macOS, double-click `DuckMail.app` to open the interactive menu in Terminal.

Run the interactive menu:

```sh
./duckmail.py
```

The interactive menu redraws in place after each action, so the terminal does
not keep scrolling while you use it.

Generate a new address:

```sh
./duckmail.py new
```

Generate a new address and save a label:

```sh
./duckmail.py new --label github
```

Same thing, as a more explicit command:

```sh
./duckmail.py new-with-label github
```

Show the last generated address:

```sh
./duckmail.py show
```

List all locally remembered addresses:

```sh
./duckmail.py list
```

Example output:

```text
Saved Duck addresses
--------------------
LABEL       ADDRESS              CREATED
----------  -------------------  ----------------
github      example@duck.com     2026-05-01 at 22:44
```

Search labels and addresses:

```sh
./duckmail.py find github
```

Change an existing label by address or current label:

```sh
./duckmail.py relabel example@duck.com banking
./duckmail.py relabel old-label new-label
```

Show the config path:

```sh
./duckmail.py where
```

Use a custom config path:

```sh
./duckmail.py new --config /path/to/config.json
```

History is stored locally in the same config file. DuckDuckGo does not provide a
stable dashboard/API for listing every generated Private Duck Address, so keep
this file backed up if you rely on the labels. Timestamps are shown in local
time as `YYYY-MM-DD at HH:MM`.

## Author

Created by [buhusa](https://x.com/buhusa).

## License

MIT
