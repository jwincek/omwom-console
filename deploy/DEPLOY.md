# Deploying OMWOM Console to the VPS

## 1. Create system user

```bash
sudo useradd -r -s /usr/sbin/nologin -d /opt/omwom-console -m consoleapp
```

## 2. Set up directory structure

```bash
sudo mkdir -p /opt/omwom-console/{app,venv}
sudo chown -R consoleapp:consoleapp /opt/omwom-console
```

## 3. Transfer application code

```bash
# From local machine
scp -P 2222 -r omwom-console/ sysadmin@YOUR_VPS_IP:/tmp/omwom-console

# On the server
sudo cp -r /tmp/omwom-console/* /opt/omwom-console/app/
sudo chown -R consoleapp:consoleapp /opt/omwom-console/app
rm -rf /tmp/omwom-console
```

## 4. Python virtual environment

```bash
sudo -u consoleapp python3 -m venv /opt/omwom-console/venv
sudo -u consoleapp /opt/omwom-console/venv/bin/pip install --upgrade pip
sudo -u consoleapp /opt/omwom-console/venv/bin/pip install -r /opt/omwom-console/app/requirements.txt
```

## 5. Environment configuration

```bash
sudo cp /opt/omwom-console/app/.env.example /opt/omwom-console/.env
sudo nano /opt/omwom-console/.env
```

Set the Semaphore API token. To generate one in Semaphore:

1. Log in to ops.omwom.com
2. Go to your user settings (top-right menu)
3. Under "API Tokens", create a new token
4. Copy the token into the `.env` file

```bash
sudo chmod 600 /opt/omwom-console/.env
sudo chown consoleapp:consoleapp /opt/omwom-console/.env
```

## 6. Install systemd service

```bash
sudo cp /opt/omwom-console/app/deploy/omwom-console.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable omwom-console
sudo systemctl start omwom-console
```

Verify:

```bash
sudo systemctl status omwom-console
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8073/
# Should return 200
```

## 7. Nginx configuration

Create HTTP basic auth credentials:

```bash
sudo htpasswd -B -c /etc/nginx/.htpasswd_console opsadmin
```

Install the Nginx config:

```bash
sudo cp /opt/omwom-console/app/deploy/console.omwom.com.conf /etc/nginx/conf.d/
sudo nginx -t
sudo systemctl reload nginx
```

## 8. DNS

Add an A record for `console.omwom.com` pointing to your VPS IP.
If using wildcard DNS (`*.omwom.com`), this is already covered.

## 9. SSL certificate

```bash
sudo certbot --nginx -d console.omwom.com
```

## 10. Verify

```bash
curl -I https://console.omwom.com
# Should return 401 (auth required)

curl -u opsadmin:YOUR_PASSWORD https://console.omwom.com
# Should return 200
```

Visit `https://console.omwom.com` in your browser and log in.

## Updating the console

```bash
# Transfer new code
scp -P 2222 -r omwom-console/ sysadmin@YOUR_VPS_IP:/tmp/omwom-console

# On the server
sudo systemctl stop omwom-console
sudo cp -r /tmp/omwom-console/* /opt/omwom-console/app/
sudo chown -R consoleapp:consoleapp /opt/omwom-console/app
sudo -u consoleapp /opt/omwom-console/venv/bin/pip install -r /opt/omwom-console/app/requirements.txt
sudo systemctl start omwom-console
rm -rf /tmp/omwom-console
```

## Monitoring

Add to Uptime Kuma at status.omwom.com:
- URL: `https://console.omwom.com/healthz`
- Interval: 60s
- Auth: HTTP Basic (opsadmin)

## Fail2ban (optional)

Add a jail for brute-force protection on the Nginx basic auth:

```bash
sudo nano /etc/fail2ban/jail.d/console.conf
```

```ini
[nginx-http-auth-console]
enabled = true
port = http,https
filter = nginx-http-auth
logpath = /var/log/nginx/error.log
maxretry = 5
bantime = 3600
```

```bash
sudo systemctl restart fail2ban
```
