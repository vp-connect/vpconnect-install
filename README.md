# vpconnect-install

Python tool to provision a **Ubuntu 22.04** (or compatible) server over **SSH**: optional new root password / SSH port / extra `authorized_keys`, **UFW** (enabled only at the **end**), **WireGuard**, **Telegram MTProxy** (systemd unit `mtproxy`), and a **git-based Python app** (VPManage-style, `uvicorn main:app`). Entry points: **CLI**, **Tkinter GUI**, or **PyInstaller** `.exe`.

> **Risk:** Changing SSH port, firewall, or passwords can lock you out. Keep provider **console** access and test on a disposable VM first. There is **no dry-run** mode: a run performs real SSH and remote changes.

## Requirements (operator machine)

- Python **3.10+**
- Network access to the server SSH port and (by default) **GitHub** `raw.githubusercontent.com` to download provisioning shell scripts for your app version

On **Windows**, use **Git Bash** or **WSL** for `bootstrap.sh`, or install Python and use `pip` / `venv`.

## Version and script branch

The package version (`vpconnect_install.version.__version__`) selects the **Git branch** in the scripts repository via `scripts_git_branch()` (for example `0.1.0` → `v0.1.0`; versions containing `dev` → `main`). Ensure that branch exists in your scripts repo or downloads fall back to **embedded** copies from the wheel/exe.

## Quick start

```sh
./bootstrap.sh
. .venv/bin/activate
python -m vpconnect_install --help
```

## CLI

**Authentication:** try `--root-private-key` first, then `ROOT_PASSWORD` / `--root-password`.

**`--auto-setup` (default):** enables WireGuard + MTProxy + VPManage, generates new root password and SSH port **2222** (if not set), uses **public IP on the server** for URLs when no `--domain` / `--domain-client-key`, generates `VPM_PASSWORD` if needed.

**`--no-auto-setup`:** use `--set-wireguard` / `--set-mtproxy` / `--set-vpmanage` explicitly. Omit `--new-ssh-port` to leave the SSH port unchanged.

**Effective host / domain (APP_DOMAIN):**

1. `--domain` (FQDN) if set  
2. else `--domain-client-key` / `DOMAIN_CLIENT_KEY` — HTTP call to `DOMAIN_CLIENT_SERVICE_URL` (see `defaults.py`)  
3. else **`--use-public-ip`** or **`--auto-setup`** → detect public IP on the server  
4. else SSH **host**

**Scripts repo (separate from VPManage `git clone` on the server):** `--scripts-repo-url` (default in `defaults.SCRIPTS_REPO_URL_DEFAULT`). Scripts are expected under `remote/<name>.sh` in that GitHub repo.

Example (manual groups, optional new SSH port):

```sh
python -m vpconnect_install --host 203.0.113.10 --no-auto-setup \
  --root-password-file /secure/root.txt \
  --set-wireguard --set-mtproxy --set-vpmanage \
  --new-ssh-port 2222 --new-root-password-file /secure/new.txt \
  --domain example.com
```

Environment variables (optional): `ROOT_PASSWORD`, `NEW_ROOT_PASSWORD`, `VPM_PASSWORD`, `ROOT_KEY_PASSPHRASE`, `DOMAIN_CLIENT_KEY`.

## GUI

```sh
python -m vpconnect_install gui
```

- **Упрощённый** mode: connection fields only; same as `auto_setup`.
- **Расширенный**: groups (connection tuning, domain, **GitHub scripts repo URL**, WireGuard, MTProxy, VPManage) with enable checkboxes. Domain: FQDN and/or **ключ сервиса домена**; if both empty while «Настроить домен» is on, behavior matches public-IP detection.

## Remote flow (no named “phases”)

1. `base_ufw_prepare.sh` — `apt update`, `ufw allow …` only (**no** `ufw enable`).
2. `connect_tune.sh` — optional `chpasswd`, sshd drop-in, `authorized_keys` (**no** `sshd` restart).
3. Optional: `wireguard_install.sh`, `mtproxy_install.sh`, `vpmanage_install.sh`.
4. `finalize.sh` — **`systemctl restart ssh`**, **`ufw --force enable`**, then status output (WireGuard, `mtproxy`, `mtproxy.link`, VPManage URL).

Bundled copies live under `src/vpconnect_install/remote/`; at runtime the app prefers downloads from the configured GitHub repo (same filenames, under `remote/` in the repo).

## Local artifacts

Under `provision-artifacts/<host>-<timestamp>/`:

- `ACCESS.txt` — summary, SSH command, ports, URLs.
- `credentials_new_root_password.txt` / `credentials_vpm_password.txt` when applicable.
- `id_ed25519` / `id_ed25519.pub` — operator key generated for this run (public key is added on the server).

## Distribution builds

**Windows GUI exe + `readme.txt` + portable source zip** (under `dist/`):

```sh
pip install -r requirements-dev.txt
pip install -e .
python packaging/build_distribution.py
```

Artifacts:

- `dist/vpconnect-install-gui.exe`
- `dist/readme.txt` — short notes for the exe
- `dist/vpconnect-install-portable.zip` — `src/`, `packaging/`, `pyproject.toml`, `README.md`, requirements, `scripts/install_venv.sh`, `scripts/install_venv.bat`

Portable zip: unpack, run `scripts/install_venv.sh` or `install_venv.bat`, then `python -m vpconnect_install gui` or CLI.

PyInstaller only (without full dist script):

```powershell
pip install -r requirements-dev.txt
.\scripts\build_gui_exe.ps1
```

IntelliJ: run configuration **Build full distribution** (`.run/Build full distribution.run.xml`).

## Defaults and tuning

Edit [`src/vpconnect_install/defaults.py`](src/vpconnect_install/defaults.py) for VPManage git URL, scripts repo default, domain service URL, install path, default ports, MTProxy unit name, timeouts, and auto-setup behavior.

## Tests

```sh
pip install -r requirements-test.txt
pip install -e .
pytest
```
