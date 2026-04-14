"""
DNS record checker for managed domains.

Verifies A, MX, SPF, DKIM, and DMARC records are properly configured.
Uses live DNS lookups — works in both local dev and production.
"""

import dns.resolver
from dataclasses import dataclass


@dataclass
class DnsCheck:
    record_type: str
    name: str
    expected: str
    actual: str
    status: str  # "ok", "warning", "error", "missing"
    detail: str = ""


def _query(name: str, rdtype: str) -> list[str]:
    try:
        answers = dns.resolver.resolve(name, rdtype)
        return [str(rdata).strip('"') for rdata in answers]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        return []
    except dns.resolver.LifetimeTimeout:
        return ["TIMEOUT"]
    except Exception:
        return []


def check_a_record(domain: str, expected_ip: str = "") -> DnsCheck:
    results = _query(domain, "A")

    if not results:
        return DnsCheck("A", domain, expected_ip or "any IP", "not found", "error",
                        "No A record found. The domain won't resolve to your server.")

    actual = ", ".join(results)
    if "TIMEOUT" in results:
        return DnsCheck("A", domain, expected_ip or "any IP", "timeout", "warning",
                        "DNS lookup timed out.")

    if expected_ip and expected_ip not in results:
        return DnsCheck("A", domain, expected_ip, actual, "warning",
                        f"A record points to {actual}, expected {expected_ip}.")

    return DnsCheck("A", domain, expected_ip or "any IP", actual, "ok")


def check_mx_record(domain: str, expected_mx: str = "") -> DnsCheck:
    results = _query(domain, "MX")

    if not results:
        return DnsCheck("MX", domain, expected_mx or "any MX", "not found", "missing",
                        "No MX record. Email for this domain won't be delivered.")

    actual = ", ".join(results)
    if expected_mx and not any(expected_mx.rstrip(".") in r for r in results):
        return DnsCheck("MX", domain, expected_mx, actual, "warning",
                        f"MX doesn't point to {expected_mx}.")

    return DnsCheck("MX", domain, expected_mx or "any MX", actual, "ok")


def check_spf(domain: str, expected_include: str = "") -> DnsCheck:
    results = _query(domain, "TXT")
    spf_records = [r for r in results if r.startswith("v=spf1")]

    if not spf_records:
        return DnsCheck("SPF", domain, "v=spf1 ...", "not found", "error",
                        "No SPF record. Email from this domain may be marked as spam.")

    spf = spf_records[0]
    if expected_include and expected_include not in spf:
        return DnsCheck("SPF", domain, f"contains {expected_include}", spf, "warning",
                        f"SPF record doesn't include {expected_include}.")

    if "-all" in spf:
        return DnsCheck("SPF", domain, "v=spf1 ...", spf, "ok", "Hard fail policy.")
    elif "~all" in spf:
        return DnsCheck("SPF", domain, "v=spf1 ...", spf, "ok", "Soft fail policy.")
    elif "?all" in spf:
        return DnsCheck("SPF", domain, "v=spf1 ...", spf, "warning",
                        "Neutral policy — consider ~all or -all.")

    return DnsCheck("SPF", domain, "v=spf1 ...", spf, "ok")


DKIM_SELECTORS = ["modoboa", "default", "mail", "google", "dkim", "smtpapi", "s1", "k1"]


def check_dkim(domain: str, selectors: list[str] | None = None) -> DnsCheck:
    selectors_to_try = selectors or DKIM_SELECTORS

    for selector in selectors_to_try:
        dkim_name = f"{selector}._domainkey.{domain}"
        results = _query(dkim_name, "TXT")

        if not results:
            continue

        dkim = results[0]
        if "p=" in dkim:
            key_fragment = dkim[dkim.index("p="):dkim.index("p=") + 20] + "..."
            return DnsCheck("DKIM", dkim_name, "DKIM key", key_fragment, "ok",
                            f"DKIM key found (selector: `{selector}`)")

        return DnsCheck("DKIM", dkim_name, "DKIM key", dkim[:60] + "...", "warning",
                        f"TXT record at `{dkim_name}` exists but doesn't look like a DKIM key.")

    tried = ", ".join(f"`{s}`" for s in selectors_to_try)
    return DnsCheck("DKIM", f"*._domainkey.{domain}", "DKIM key", "not found", "missing",
                    f"No DKIM record found. Tried selectors: {tried}.")


def check_dmarc(domain: str) -> DnsCheck:
    dmarc_name = f"_dmarc.{domain}"
    results = _query(dmarc_name, "TXT")
    dmarc_records = [r for r in results if r.startswith("v=DMARC1")]

    if not dmarc_records:
        return DnsCheck("DMARC", dmarc_name, "v=DMARC1 ...", "not found", "missing",
                        "No DMARC record. Email authentication reporting won't work.")

    dmarc = dmarc_records[0]
    if "p=reject" in dmarc:
        policy = "reject"
    elif "p=quarantine" in dmarc:
        policy = "quarantine"
    elif "p=none" in dmarc:
        policy = "none"
    else:
        policy = "unknown"

    if policy == "none":
        return DnsCheck("DMARC", dmarc_name, "v=DMARC1 ...", dmarc, "warning",
                        "Policy is 'none' — no enforcement. Consider 'quarantine' or 'reject'.")

    return DnsCheck("DMARC", dmarc_name, "v=DMARC1 ...", dmarc, "ok",
                    f"Policy: {policy}")


def check_domain(domain: str, expected_ip: str = "", mail_server: str = "") -> list[DnsCheck]:
    checks = [
        check_a_record(domain, expected_ip),
        check_mx_record(domain, mail_server),
        check_spf(domain, mail_server),
        check_dkim(domain),
        check_dmarc(domain),
    ]
    return checks
