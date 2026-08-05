# NETWORK TOOLS - Linux Deployment

This app runs as one Django service. Use these steps after `git pull` on the Linux server.

## 1. Install system packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

## 2. Clone or pull the repo

First time:

```bash
cd /opt
sudo git clone https://github.com/riz-coder/Network-Tools network-dashboard
sudo chown -R $USER:$USER /opt/network-dashboard
cd /opt/network-dashboard
```

Existing server:

```bash
cd /opt/network-dashboard
git pull
```

## 3. Create venv and install requirements

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Prepare database

```bash
python manage.py migrate
```

Create/update the root operator user:

```bash
python manage.py shell -c "from django.contrib.auth.models import User; u, _ = User.objects.get_or_create(username='rizwan'); u.set_password('RIzwan23#$%'); u.is_staff=True; u.is_superuser=True; u.save(); User.objects.exclude(username='rizwan').update(is_staff=False, is_superuser=False)"
```

Fix SQLite and local runtime file permissions for the service user:

```bash
sudo chown -R $USER:$USER /opt/network-dashboard
chmod 664 /opt/network-dashboard/db.sqlite3
chmod 775 /opt/network-dashboard
touch activity_log.json mac_cache.json
chmod 664 activity_log.json mac_cache.json
```

If you run the systemd service with another user, replace `$USER` with that service user and run:

```bash
sudo chown -R YOUR_LINUX_USER:YOUR_LINUX_USER /opt/network-dashboard
```

## 5. Run the app

For quick manual run:

```bash
source .venv/bin/activate
python manage.py runserver 0.0.0.0:8501
```

Open:

```text
http://SERVER_IP:8501
```

## 6. Optional systemd service

Create service file:

```bash
sudo nano /etc/systemd/system/network-tools.service
```

Paste:

```ini
[Unit]
Description=NETWORK TOOLS Django Service
After=network.target

[Service]
WorkingDirectory=/opt/network-dashboard
ExecStart=/opt/network-dashboard/.venv/bin/python manage.py runserver 0.0.0.0:8501
Restart=always
RestartSec=5
User=YOUR_LINUX_USER
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Replace `YOUR_LINUX_USER` with the Linux username.

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable network-tools
sudo systemctl restart network-tools
sudo systemctl status network-tools
```

View logs:

```bash
journalctl -u network-tools -f
```

## Notes

- Do not commit `db.sqlite3`, `.venv`, `activity_log.json`, or `mac_cache.json`.
- The app listens on one port only: `8501`.
- Telnet access must be allowed from the Linux server to the switches.
- TFTP/HTTP IOS source must be reachable from the Linux server and switches.
