"""
Mock log data for local development.

In production, these would be read from actual log files via SSH or a
log-reading API endpoint on the server:
- /var/log/backup.log
- /var/log/backup-verify.log
- /var/log/mail.log
- /var/log/nginx/*.log
- /var/log/ssl-report.json
- /var/log/wp-updates.log
"""

from datetime import datetime, timedelta, timezone


def _generate_timestamps(count: int, interval_sec: int = 60):
    now = datetime.now(timezone.utc)
    return [now - timedelta(seconds=i * interval_sec) for i in range(count)]


def get_log_sources():
    return [
        {
            "name": "Backup",
            "file": "/var/log/backup.log",
            "description": "Daily backup orchestration (backup_manager.py)",
        },
        {
            "name": "Backup Verify",
            "file": "/var/log/backup-verify.log",
            "description": "Backup integrity verification (backup_verify.py)",
        },
        {
            "name": "Mail",
            "file": "/var/log/mail.log",
            "description": "Postfix/Dovecot mail delivery",
        },
        {
            "name": "Nginx Error",
            "file": "/var/log/nginx/error.log",
            "description": "Nginx error log (all sites)",
        },
        {
            "name": "Nginx Access",
            "file": "/var/log/nginx/access.log",
            "description": "Nginx access log (all sites)",
        },
        {
            "name": "WordPress Updates",
            "file": "/var/log/wp-updates.log",
            "description": "Weekly WordPress update results (wp-update-all.sh)",
        },
        {
            "name": "Fail2ban",
            "file": "/var/log/fail2ban.log",
            "description": "Intrusion prevention bans and unbans",
        },
        {
            "name": "Auth",
            "file": "/var/log/auth.log",
            "description": "SSH and system authentication",
        },
    ]


_BACKUP_LOG = """2026-04-11 02:00:03 [INFO] ========== Backup run started ==========
2026-04-11 02:00:03 [INFO] Staging directory: /var/backups/staging
2026-04-11 02:00:04 [INFO] Dumping MariaDB databases...
2026-04-11 02:00:04 [INFO]   slowbread_db: 245 MB (12.3s)
2026-04-11 02:00:17 [INFO]   wp2_db: 89 MB (4.1s)
2026-04-11 02:00:21 [INFO]   wp3_db: 34 MB (1.8s)
2026-04-11 02:00:23 [INFO] Dumping PostgreSQL databases...
2026-04-11 02:00:23 [INFO]   odoo1_db: 512 MB (28.4s)
2026-04-11 02:00:52 [INFO]   odoo2_db: 387 MB (19.2s)
2026-04-11 02:01:11 [INFO]   semaphore: 28 MB (1.2s)
2026-04-11 02:01:12 [INFO]   modoboa: 156 MB (8.7s)
2026-04-11 02:01:21 [INFO]   oilregion_db: 67 MB (3.4s)
2026-04-11 02:01:24 [INFO] Database dumps complete: 8 databases, 1518 MB
2026-04-11 02:01:25 [INFO] Archiving file backups...
2026-04-11 02:01:25 [INFO]   /var/www/ → wordpress_sites.tar.gz (892 MB)
2026-04-11 02:02:45 [INFO]   /opt/odoo/data/ → odoo_data.tar.gz (634 MB)
2026-04-11 02:03:30 [INFO]   /opt/odoo/custom-addons/ → odoo_addons.tar.gz (45 MB)
2026-04-11 02:03:35 [INFO]   /var/vmail/ → mail_data.tar.gz (1240 MB)
2026-04-11 02:05:10 [INFO] File backups complete: 4 archives, 2811 MB
2026-04-11 02:05:11 [INFO] Generating checksums...
2026-04-11 02:05:14 [INFO] Checksums written to /var/backups/checksums.json
2026-04-11 02:05:15 [INFO] Uploading to Backblaze B2...
2026-04-11 02:06:42 [INFO]   Backblaze B2: 12 files uploaded (2847 MB)
2026-04-11 02:06:43 [INFO] Uploading to Hetzner...
2026-04-11 02:08:05 [INFO]   Hetzner: 12 files uploaded (2847 MB)
2026-04-11 02:08:06 [INFO] Pruning old local backups (>7 days)...
2026-04-11 02:08:06 [INFO]   Removed 12 files from 2026-04-04
2026-04-11 02:08:07 [INFO] ========== Backup run complete ==========
2026-04-11 02:08:07 [INFO] Duration: 8m 4s | Total size: 2847 MB | Status: SUCCESS"""

_VERIFY_LOG = """2026-04-11 05:00:12 [INFO] ========== Verification: local ==========
2026-04-11 05:00:12 [INFO] Checking local checksums...
2026-04-11 05:00:14 [INFO]   slowbread_db.sql.gz: SHA256 OK
2026-04-11 05:00:14 [INFO]   wp2_db.sql.gz: SHA256 OK
2026-04-11 05:00:14 [INFO]   wp3_db.sql.gz: SHA256 OK
2026-04-11 05:00:15 [INFO]   odoo1_db.custom.gz: SHA256 OK
2026-04-11 05:00:16 [INFO]   odoo2_db.custom.gz: SHA256 OK
2026-04-11 05:00:16 [INFO]   semaphore.custom.gz: SHA256 OK
2026-04-11 05:00:16 [INFO]   modoboa.custom.gz: SHA256 OK
2026-04-11 05:00:17 [INFO]   oilregion_db.custom.gz: SHA256 OK
2026-04-11 05:00:18 [INFO]   wordpress_sites.tar.gz: SHA256 OK
2026-04-11 05:00:20 [INFO]   odoo_data.tar.gz: SHA256 OK
2026-04-11 05:00:20 [INFO]   odoo_addons.tar.gz: SHA256 OK
2026-04-11 05:00:22 [INFO]   mail_data.tar.gz: SHA256 OK
2026-04-11 05:00:22 [INFO] All 12 files verified: 0 errors
2026-04-11 05:00:22 [INFO] Duration: 10s | Status: PASSED"""

_MAIL_LOG = """Apr 11 08:14:22 mail postfix/smtpd[12345]: connect from unknown[203.0.113.45]
Apr 11 08:14:23 mail postfix/smtpd[12345]: NOQUEUE: reject: RCPT from unknown[203.0.113.45]: 554 5.7.1 <spammer@example.com>: Relay access denied
Apr 11 08:14:23 mail postfix/smtpd[12345]: disconnect from unknown[203.0.113.45]
Apr 11 09:22:01 mail postfix/pickup[11234]: 4A3B2C1D0E: uid=1001 from=<noreply@oilregionindie.com>
Apr 11 09:22:01 mail postfix/cleanup[11235]: 4A3B2C1D0E: message-id=<20260411092201.4A3B2C1D0E@mail.omwom.com>
Apr 11 09:22:02 mail postfix/qmgr[1234]: 4A3B2C1D0E: from=<noreply@oilregionindie.com>, size=4523, nrcpt=1 (queue active)
Apr 11 09:22:03 mail postfix/smtp[11236]: 4A3B2C1D0E: to=<artist@example.com>, relay=mx.example.com[198.51.100.1]:25, delay=1.2, status=sent (250 OK)
Apr 11 09:22:03 mail postfix/qmgr[1234]: 4A3B2C1D0E: removed
Apr 11 10:05:17 mail dovecot[5678]: imap-login: Login: user=<admin@slowbirdbread.com>, method=PLAIN, rip=198.51.100.50
Apr 11 10:05:18 mail dovecot[5679]: imap(admin@slowbirdbread.com): Logged out in=342 out=5891
Apr 11 11:30:45 mail postfix/smtpd[12350]: connect from mail-sor-f41.google.com[209.85.167.41]
Apr 11 11:30:46 mail postfix/smtpd[12350]: 5B4C3D2E1F: client=mail-sor-f41.google.com[209.85.167.41]
Apr 11 11:30:46 mail postfix/cleanup[12351]: 5B4C3D2E1F: message-id=<CAFG123@mail.gmail.com>
Apr 11 11:30:47 mail postfix/qmgr[1234]: 5B4C3D2E1F: from=<customer@gmail.com>, size=8234, nrcpt=1 (queue active)
Apr 11 11:30:47 mail dovecot[5680]: lda(info@slowbirdbread.com): msgid=<CAFG123@mail.gmail.com>: saved mail to INBOX
Apr 11 11:30:47 mail postfix/pipe[12352]: 5B4C3D2E1F: to=<info@slowbirdbread.com>, relay=dovecot, delay=0.8, status=sent
Apr 11 14:12:33 mail postfix/anvil[12400]: statistics: max connection rate 3/60s for (smtp:203.0.113.0) at Apr 11 08:14:22"""

_NGINX_ERROR = """2026/04/11 03:22:15 [error] 1234#1234: *56789 open() "/var/www/wp3/public/wp-content/plugins/revslider/temp.php" failed (2: No such file or directory), client: 203.0.113.100, server: clientsite3.com, request: "GET /wp-content/plugins/revslider/temp.php HTTP/1.1"
2026/04/11 03:22:16 [error] 1234#1234: *56790 open() "/var/www/wp3/public/.env" failed (2: No such file or directory), client: 203.0.113.100, server: clientsite3.com, request: "GET /.env HTTP/1.1"
2026/04/11 07:45:33 [error] 1234#1234: *67890 upstream timed out (110: Connection timed out) while reading response header from upstream, client: 198.51.100.55, server: odoo1.example.com, request: "GET /web/dataset/call_kw HTTP/1.1", upstream: "http://127.0.0.1:8069/web/dataset/call_kw"
2026/04/11 12:01:02 [warn] 1234#1234: *78901 an upstream response is buffered to a temporary file /var/cache/nginx/proxy_temp/2/01/0000000012, client: 198.51.100.60, server: slowbirdbread.com, request: "POST /wp-admin/admin-ajax.php HTTP/1.1"
2026/04/11 15:30:44 [error] 1234#1234: *89012 limiting requests, excess: 3.456 by zone "wp_login", client: 203.0.113.200, server: slowbirdbread.com, request: "POST /wp-login.php HTTP/1.1"
2026/04/11 15:30:45 [error] 1234#1234: *89013 limiting requests, excess: 4.567 by zone "wp_login", client: 203.0.113.200, server: slowbirdbread.com, request: "POST /wp-login.php HTTP/1.1"
2026/04/11 15:30:46 [error] 1234#1234: *89014 limiting requests, excess: 5.678 by zone "wp_login", client: 203.0.113.200, server: slowbirdbread.com, request: "POST /wp-login.php HTTP/1.1"
"""

_WP_UPDATES = """2026-04-06 03:00:01 ========== WordPress Update Run ==========
2026-04-06 03:00:02 [slowbread] Checking for updates...
2026-04-06 03:00:03 [slowbread] Core: 6.9.4 (up to date)
2026-04-06 03:00:04 [slowbread] Plugins: woocommerce 9.8.1 → 9.8.2 (updated)
2026-04-06 03:00:12 [slowbread] Plugins: wpforms-lite 2.0.1 (up to date)
2026-04-06 03:00:13 [slowbread] Themes: flavor 1.2.3 (up to date)
2026-04-06 03:00:14 [wp2] Checking for updates...
2026-04-06 03:00:15 [wp2] Core: 6.9.4 (up to date)
2026-04-06 03:00:16 [wp2] Plugins: all up to date
2026-04-06 03:00:17 [wp3] Checking for updates...
2026-04-06 03:00:18 [wp3] Core: 6.8.1 → 6.9.4 available (minor update applied)
2026-04-06 03:00:35 [wp3] Core updated to 6.9.4
2026-04-06 03:00:36 [wp3] Plugins: all up to date
2026-04-06 03:00:37 ========== Update complete: 2 updates applied =========="""

_FAIL2BAN = """2026-04-11 03:22:17 fail2ban.filter  [1]: INFO    [nginx-botsearch] Found 203.0.113.100 - 2026-04-11 03:22:15
2026-04-11 03:22:18 fail2ban.filter  [1]: INFO    [nginx-botsearch] Found 203.0.113.100 - 2026-04-11 03:22:16
2026-04-11 03:22:18 fail2ban.actions [1]: NOTICE  [nginx-botsearch] Ban 203.0.113.100
2026-04-11 08:14:23 fail2ban.filter  [1]: INFO    [postfix-sasl] Found 203.0.113.45 - 2026-04-11 08:14:23
2026-04-11 15:30:44 fail2ban.filter  [1]: INFO    [wordpress-hard] Found 203.0.113.200 - 2026-04-11 15:30:44
2026-04-11 15:30:45 fail2ban.filter  [1]: INFO    [wordpress-hard] Found 203.0.113.200 - 2026-04-11 15:30:45
2026-04-11 15:30:46 fail2ban.filter  [1]: INFO    [wordpress-hard] Found 203.0.113.200 - 2026-04-11 15:30:46
2026-04-11 15:30:46 fail2ban.actions [1]: NOTICE  [wordpress-hard] Ban 203.0.113.200"""

_AUTH_LOG = """Apr 11 02:15:33 omwom sshd[45678]: Connection from 198.51.100.10 port 54321 on 10.0.0.1 port 2222 rdomain ""
Apr 11 02:15:34 omwom sshd[45678]: Accepted publickey for sysadmin from 198.51.100.10 port 54321 ssh2: ED25519 SHA256:abc123
Apr 11 02:15:34 omwom sshd[45678]: pam_unix(sshd:session): session opened for user sysadmin
Apr 11 02:45:12 omwom sshd[45678]: pam_unix(sshd:session): session closed for user sysadmin
Apr 11 06:30:01 omwom sshd[56789]: Invalid user admin from 203.0.113.150 port 12345
Apr 11 06:30:01 omwom sshd[56789]: Connection closed by invalid user admin 203.0.113.150 port 12345
Apr 11 06:30:05 omwom sshd[56790]: Invalid user root from 203.0.113.150 port 12346
Apr 11 06:30:05 omwom sshd[56790]: Connection closed by invalid user root 203.0.113.150 port 12346"""


_LOG_CONTENT = {
    "Backup": _BACKUP_LOG,
    "Backup Verify": _VERIFY_LOG,
    "Mail": _MAIL_LOG,
    "Nginx Error": _NGINX_ERROR,
    "Nginx Access": "",
    "WordPress Updates": _WP_UPDATES,
    "Fail2ban": _FAIL2BAN,
    "Auth": _AUTH_LOG,
}


def get_log_content(source_name: str, tail_lines: int = 100) -> str:
    content = _LOG_CONTENT.get(source_name, "")
    if not content:
        return f"(No mock data for {source_name})"
    lines = content.strip().split("\n")
    return "\n".join(lines[-tail_lines:])
