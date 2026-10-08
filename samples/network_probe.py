import ipaddress
import json
import os
import socket
from datetime import datetime, timezone
from email.utils import formatdate
from urllib.request import ProxyHandler, Request, build_opener


LAB_NETWORKS = tuple(
    ipaddress.ip_network(cidr)
    for cidr in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10")
)


def is_lab_private(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return any(ip in network for network in LAB_NETWORKS)


def private_dns(host: str, port: int) -> list[str]:
    addresses = sorted(
        {item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    )
    if not addresses or not all(is_lab_private(address) for address in addresses):
        raise RuntimeError(f"Non-private DNS result for {host}: {addresses}")
    return addresses


def check_marker(actual: str, expected: str) -> str:
    if not expected.strip():
        raise ValueError("Expected marker must not be empty")
    if actual.strip() != expected.strip():
        raise RuntimeError("Marker mismatch: update data and EXPECTED_MARKER consistently")
    return actual.strip()


def get_credential():
    from azure.identity import DefaultAzureCredential

    client_id = os.environ.get("DATA_IDENTITY_CLIENT_ID")
    return DefaultAzureCredential(managed_identity_client_id=client_id)


def storage_text(url: str, credential, *, files: bool = False) -> str:
    token = credential.get_token("https://storage.azure.com/.default").token
    headers = {
        "Authorization": f"Bearer {token}",
        "x-ms-date": formatdate(usegmt=True),
        "x-ms-version": "2023-11-03",
    }
    if files:
        headers["x-ms-file-request-intent"] = "backup"
    request = Request(url, headers=headers)
    opener = build_opener(ProxyHandler({}))
    with opener.open(request, timeout=30) as response:
        return response.read(4096).decode("utf-8")


def read_blob(account: str, expected: str, credential) -> dict:
    host = f"{account}.blob.core.windows.net"
    addresses = private_dns(host, 443)
    text = storage_text(f"https://{host}/labdata/marker.txt", credential)
    return {"host": host, "resolved_ips": addresses, "marker": check_marker(text, expected)}


def read_file(account: str, expected: str, credential) -> dict:
    host = f"{account}.file.core.windows.net"
    addresses = private_dns(host, 443)
    text = storage_text(f"https://{host}/labfiles/marker.txt", credential, files=True)
    return {"host": host, "resolved_ips": addresses, "marker": check_marker(text, expected)}


def read_postgres(expected: str, credential) -> dict:
    import psycopg

    host = os.environ["PGHOST"]
    addresses = private_dns(host, 5432)
    token = credential.get_token("https://ossrdbms-aad.database.windows.net/.default").token
    with psycopg.connect(
        host=host,
        port=5432,
        dbname="labdb",
        user=os.environ["PGUSER"],
        password=token,
        sslmode="verify-full",
        sslrootcert=os.environ["PGSSLROOTCERT"],
        connect_timeout=30,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT marker, inet_client_addr()::text, inet_server_addr()::text "
                "FROM public.lab_marker WHERE id = %s",
                (1,),
            )
            row = cursor.fetchone()
    if row is None:
        raise RuntimeError("public.lab_marker has no row with id=1")
    return {
        "host": host,
        "resolved_ips": addresses,
        "marker": check_marker(row[0], expected),
        "db_observed_client": row[1],
        "db_observed_server": row[2],
    }


def run_probe(*, include_files: bool = False) -> dict:
    expected = os.environ["EXPECTED_MARKER"]
    credential = get_credential()
    try:
        result = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "execution_label": os.environ["EXECUTION_LABEL"],
            "blob": read_blob(os.environ["STORAGE_ACCOUNT"], expected, credential),
            "postgres": read_postgres(expected, credential),
        }
        if include_files:
            result["files"] = read_file(os.environ["STORAGE_ACCOUNT"], expected, credential)
        return result
    finally:
        credential.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--files", action="store_true", help="Also test Azure Files")
    args = parser.parse_args()
    print(json.dumps(run_probe(include_files=args.files), ensure_ascii=False, indent=2))
