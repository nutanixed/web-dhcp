# web-dhcp

A Flask-based web interface for viewing DHCP leases and managing static DHCP reservations for a `dnsmasq` host.

The app delegates DHCP operations to `list_dhcp_reservations.sh`, then renders data in a browser UI and exposes JSON endpoints for automation.

## Features

- View active DHCP leases (MAC, IP, hostname, expiry).
- View static DHCP reservations from `dnsmasq` config.
- Add static reservation (`MAC -> IP`).
- Update static reservation for an existing MAC.
- Delete static reservation by MAC.
- JSON API endpoints for data retrieval and CRUD actions.
- Optional Gunicorn watchdog restart helper (`restart.sh`).

## Project Structure

- `app.py` - Flask app, routes, auth hooks, script execution, parsing.
- `list_dhcp_reservations.sh` - Backend shell operations for list/add/update/delete.
- `restart.sh` - Restarts app under a self-healing Gunicorn loop.
- `templates/index.html` - Main DHCP manager UI.
- `templates/login.html` - Login page template (currently bypassed by app logic).
- `static/` - Static assets such as `favicon.svg`.

## Prerequisites

- Linux host with:
  - `python3`
  - `pip`
  - `dnsmasq`
  - `sudo`
  - `systemctl` (for restarting `dnsmasq`)
- Access to DHCP lease/config files:
  - `/var/lib/misc/dnsmasq.leases`
  - `/etc/dnsmasq.d/dhcp_reservations.conf`

## Python Dependencies

Install required packages:

```bash
pip install flask ldap3 python-dotenv gunicorn
```

If you prefer virtual environments:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install flask ldap3 python-dotenv gunicorn
```

## Configuration

Create a `.env` file in the project root (`/home/nutanix/web-dhcp/.env`).

### Supported Environment Variables

- `SECRET_KEY` - Flask session key.
- `AUTH_USERNAME` - Local username (used only when login flow is enabled).
- `AUTH_PASSWORD` - Local password (used only when login flow is enabled).
- `LDAP_SERVER` - LDAP server URL/host.
- `LDAP_ADMIN_DN` - LDAP bind DN for user lookup.
- `LDAP_ADMIN_PASSWORD` - LDAP bind password.
- `LDAP_USER_SEARCH_BASE` - LDAP search base DN.
- `LDAP_USER_ATTRIBUTE` - LDAP user attribute (for example `sAMAccountName`).
- `LOGOUT_REDIRECT_URL` - Redirect target after logout (default `/`).

Example:

```env
SECRET_KEY=change-me
AUTH_USERNAME=admin
AUTH_PASSWORD=change-me
LDAP_SERVER=ldap://your-ldap-server
LDAP_ADMIN_DN=cn=admin,dc=example,dc=com
LDAP_ADMIN_PASSWORD=change-me
LDAP_USER_SEARCH_BASE=ou=users,dc=example,dc=com
LDAP_USER_ATTRIBUTE=sAMAccountName
LOGOUT_REDIRECT_URL=/
```

## Run the Application

### Development (Flask built-in server)

```bash
cd /home/nutanix/web-dhcp
python3 app.py
```

The app listens on:

- `http://0.0.0.0:5001`

### Production-style (Gunicorn)

```bash
cd /home/nutanix/web-dhcp
gunicorn --bind 0.0.0.0:5001 --workers 4 --timeout 300 app:app
```

### Restart Helper Script

`restart.sh`:

- Kills existing matching Gunicorn/watchdog processes.
- Starts a watchdog loop that restarts Gunicorn if it exits.
- Writes logs to `/tmp/web-dhcp.log` and Gunicorn log files in `/tmp/`.

Run:

```bash
cd /home/nutanix/web-dhcp
bash restart.sh
```

## API Endpoints

All endpoints require authenticated session behavior from the app.

- `GET /`  
  Render UI with leases and reservations.

- `GET /api/data`  
  Returns:
  ```json
  {
    "leases": [
      {"mac":"50:6b:8d:7b:10:c0","ip":"10.142.152.198","hostname":"host1","expiry":"2026-03-26 10:26:40"}
    ],
    "reservations": [
      {"mac":"aa:bb:cc:dd:ee:ff","ip":"10.142.152.171"}
    ]
  }
  ```

- `POST /add`  
  Add reservation. Accepts form data or JSON:
  ```json
  {"mac":"aa:bb:cc:dd:ee:ff","ip":"10.142.152.171"}
  ```

- `POST /update`  
  Update reservation IP for existing MAC. Accepts form data or JSON.

- `GET /delete/<mac>` or `DELETE /delete/<mac>`  
  Remove reservation by MAC.

## Shell Script Operations

`list_dhcp_reservations.sh` supports:

```bash
./list_dhcp_reservations.sh list
./list_dhcp_reservations.sh add <mac> <ip>
./list_dhcp_reservations.sh update <mac> <ip>
./list_dhcp_reservations.sh del <mac>
```

## Important Security Notes

Current implementation includes security shortcuts that should be addressed before production use:

- Login is currently bypassed in `app.py` (`before_request` auto-login + `/login` immediate redirect).
- `app.py` has a hardcoded fallback `SECRET_KEY`.
- `list_dhcp_reservations.sh` currently contains a plaintext sudo password variable (`PASS=...`).
- Script-based shell execution is not hardened with strict input validation.

Recommended hardening:

- Re-enable real authentication flow (LDAP/local as intended).
- Require strong, environment-only secrets.
- Replace password piping with least-privilege `sudoers` rules for specific commands.
- Add MAC/IP validation before shell invocation.
- Run behind reverse proxy with TLS and network access controls.

## Troubleshooting

- **Reservations not updating**
  - Verify `dnsmasq` service is present and restartable: `sudo systemctl status dnsmasq`
  - Ensure `/etc/dnsmasq.d/dhcp_reservations.conf` exists and is writable via expected sudo path.

- **No lease data shown**
  - Confirm lease file exists and is readable: `/var/lib/misc/dnsmasq.leases`
  - Check script output directly: `./list_dhcp_reservations.sh list`

- **App starts but UI actions fail**
  - Inspect Flask/Gunicorn logs and script stderr output.
  - Ensure executable bit is set on script:
    ```bash
    chmod +x list_dhcp_reservations.sh
    ```

## License

Add your project license information here (for example, MIT, Apache-2.0, or internal-only).
