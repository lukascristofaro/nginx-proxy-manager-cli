# nginx-proxy-manager-cli

A command line client for [Nginx Proxy Manager](https://nginxproxymanager.com/) (NPM).
Manage proxy hosts, redirections, 404 hosts, streams, SSL certificates, access lists and users
from your terminal or from scripts.

## Installation

Requires Python 3.9+.

```sh
pip install .            # or: pip install -e .  for development
npm-cli --help
```

Without installing: `pip install -r requirements.txt` then `python main.py --help` (or `python -m npm_cli`).

## Authentication

```sh
npm-cli login --url http://192.168.1.10:81
```

You are prompted for your email and password. Only the session token is stored (never the password),
in `%APPDATA%\npm-cli\config.json` on Windows and `~/.config/npm-cli/config.json` elsewhere.
Tokens are refreshed automatically when they get close to expiry.

For scripts and CI you can use environment variables instead:

| Variable | Purpose |
|---|---|
| `NPM_URL` | NPM admin URL |
| `NPM_EMAIL` / `NPM_PASSWORD` | log in automatically when no valid session exists |
| `NPM_TOKEN` | use this bearer token directly |
| `NPM_CLI_CONFIG_DIR` | where to store the session file |

`npm-cli status` shows the server version and the current session, `npm-cli logout` deletes it.

## Usage

Global options work anywhere on the command line: `--json` (raw JSON output), `--url`, `--timeout`,
`-k/--insecure` (self-signed HTTPS).

### Proxy hosts

```sh
npm-cli proxy list
npm-cli proxy list --search example
npm-cli proxy show 3

# Create, requesting a Let's Encrypt certificate and forcing HTTPS
npm-cli proxy create -d app.example.com -d www.app.example.com \
  --forward-host 10.0.0.5 --forward-port 8080 \
  --ssl --email me@example.com --force-ssl --http2

# Update only what you pass
npm-cli proxy update 3 --forward-port 9000 --no-caching
npm-cli proxy update 3 --advanced-config @custom.conf

npm-cli proxy disable 3 4
npm-cli proxy enable 3
npm-cli proxy delete 3 --yes
```

Useful create/update options: `--scheme http|https`, `--websockets/--no-websockets`,
`--block-exploits/--no-block-exploits`, `--caching`, `--access-list-id ID`, `--certificate-id ID`,
`--hsts`, `--hsts-subdomains`.

### Redirections, 404 hosts and streams

They share the same `list / show / create / update / delete / enable / disable` commands.

```sh
npm-cli redirect create -d old.example.com --to new.example.com --code 301
npm-cli dead create -d unused.example.com
npm-cli stream create --incoming-port 2222 --forward-host 10.0.0.2 --forward-port 22
npm-cli stream create --incoming-port 53 --forward-host 10.0.0.3 --forward-port 53 --udp --no-tcp
```

### Certificates

```sh
npm-cli cert list
npm-cli cert create -d example.com -d '*.example.com' --email me@example.com \
  --dns-provider cloudflare --dns-credentials @cloudflare.ini
npm-cli cert upload --name "Internal CA" --cert cert.pem --key key.pem
npm-cli cert renew 5
npm-cli cert download 5 -o example.zip
npm-cli cert delete 5
```

### Access lists and users

```sh
npm-cli acl list
npm-cli acl create --name lan-only --allow 192.168.0.0/16 --deny all
npm-cli acl create --name team --user alice:secret --user bob:secret

npm-cli user list
npm-cli user create --name "Jane Doe" --email jane@example.com --admin
npm-cli user password 2
npm-cli whoami
```

### Other

```sh
npm-cli report          # number of hosts by type
npm-cli audit -n 50     # audit log
npm-cli settings
```

## Development

```sh
python -m unittest discover -s tests
```
