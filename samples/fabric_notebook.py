# Paste into a Fabric Spark notebook after uploading network_probe.py.
import importlib.util
import json
import time

from azure.core.credentials import AccessToken


STORAGE_ACCOUNT = "stffnw<suffix>"
EXPECTED_MARKER = "lab-20261008-001"
INCLUDE_FILES = False

spec = importlib.util.spec_from_file_location(
    "network_probe", "/lakehouse/default/Files/lab/network_probe.py"
)
if spec is None or spec.loader is None:
    raise RuntimeError("Cannot load uploaded network_probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class NotebookStorageCredential:
    def get_token(self, *scopes, **kwargs):
        if scopes != ("https://storage.azure.com/.default",):
            raise ValueError("This notebook credential supports only Azure Storage")
        token = notebookutils.credentials.getToken("storage")
        payload = token.split(".")[1]
        import base64

        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        expiry = int(claims["exp"])
        if expiry <= int(time.time()):
            raise RuntimeError("Notebook storage token has expired")
        return AccessToken(token, expiry)


credential = NotebookStorageCredential()
result = {
    "execution_label": "fabric-notebook-interactive",
    "blob": probe.read_blob(STORAGE_ACCOUNT, EXPECTED_MARKER, credential),
}
if INCLUDE_FILES:
    result["files"] = probe.read_file(STORAGE_ACCOUNT, EXPECTED_MARKER, credential)
print(json.dumps(result, ensure_ascii=False, indent=2))
