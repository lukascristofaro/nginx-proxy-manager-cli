"""HTTP client for the Nginx Proxy Manager REST API."""

from __future__ import annotations

from typing import Any, Iterable, Optional

import requests

from . import __version__


class NpmError(Exception):
    """Base error shown to the user without a traceback."""


class ApiError(NpmError):
    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


def normalize_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if "://" not in url:
        url = f"http://{url}"
    if url.endswith("/api"):
        url = url[: -len("/api")]
    return url


class Resource:
    """Standard CRUD endpoints shared by most NPM objects."""

    def __init__(self, client: "NpmClient", path: str):
        self.client = client
        self.path = path

    def list(self, expand: Iterable[str] = (), query: Optional[str] = None) -> list:
        params = {}
        if expand:
            params["expand"] = ",".join(expand)
        if query:
            params["query"] = query
        return self.client.get(self.path, params=params)

    def get(self, obj_id: int, expand: Iterable[str] = ()) -> dict:
        params = {"expand": ",".join(expand)} if expand else None
        return self.client.get(f"{self.path}/{obj_id}", params=params)

    def create(self, payload: dict, timeout: Optional[float] = None) -> dict:
        return self.client.post(self.path, json=payload, timeout=timeout)

    def update(self, obj_id: int, payload: dict, timeout: Optional[float] = None) -> dict:
        return self.client.put(f"{self.path}/{obj_id}", json=payload, timeout=timeout)

    def delete(self, obj_id: int) -> Any:
        return self.client.delete(f"{self.path}/{obj_id}")

    def enable(self, obj_id: int) -> Any:
        return self.client.post(f"{self.path}/{obj_id}/enable")

    def disable(self, obj_id: int) -> Any:
        return self.client.post(f"{self.path}/{obj_id}/disable")


class NpmClient:
    # Let's Encrypt validation can take a while
    CERTIFICATE_TIMEOUT = 300.0

    def __init__(self, base_url: str, token: Optional[str] = None, timeout: float = 30.0, verify: bool = True):
        self.base_url = normalize_url(base_url)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = verify
        self.session.headers["User-Agent"] = f"npm-cli/{__version__}"
        self.token = token

        self.proxy_hosts = Resource(self, "/nginx/proxy-hosts")
        self.redirection_hosts = Resource(self, "/nginx/redirection-hosts")
        self.dead_hosts = Resource(self, "/nginx/dead-hosts")
        self.streams = Resource(self, "/nginx/streams")
        self.certificates = Resource(self, "/nginx/certificates")
        self.access_lists = Resource(self, "/nginx/access-lists")
        self.users = Resource(self, "/users")

    @property
    def token(self) -> Optional[str]:
        return self._token

    @token.setter
    def token(self, value: Optional[str]) -> None:
        self._token = value
        if value:
            self.session.headers["Authorization"] = f"Bearer {value}"
        else:
            self.session.headers.pop("Authorization", None)

    def request(self, method: str, path: str, *, params=None, json=None, files=None,
                timeout: Optional[float] = None, raw: bool = False) -> Any:
        url = f"{self.base_url}/api{path}"
        try:
            response = self.session.request(
                method, url, params=params, json=json, files=files, timeout=timeout or self.timeout
            )
        except requests.exceptions.SSLError as exc:
            raise ApiError(f"TLS error while contacting {self.base_url}: {exc} (use --insecure for self-signed certificates)")
        except requests.exceptions.Timeout:
            raise ApiError(f"Request to {url} timed out")
        except requests.exceptions.RequestException as exc:
            raise ApiError(f"Cannot reach {self.base_url}: {exc}")

        if not response.ok:
            raise ApiError(_error_message(response), response.status_code)
        if raw:
            return response
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    def get(self, path: str, **kwargs) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> Any:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> Any:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs) -> Any:
        return self.request("DELETE", path, **kwargs)

    # --- auth ---------------------------------------------------------------

    def login(self, identity: str, secret: str) -> dict:
        data = self.post("/tokens", json={"identity": identity, "secret": secret})
        self.token = data["token"]
        return data

    def refresh_token(self) -> dict:
        data = self.get("/tokens")
        self.token = data["token"]
        return data

    def me(self) -> dict:
        return self.get("/users/me")

    def health(self) -> dict:
        return self.get("/")

    # --- certificates -------------------------------------------------------

    def renew_certificate(self, cert_id: int) -> dict:
        return self.post(f"/nginx/certificates/{cert_id}/renew", timeout=self.CERTIFICATE_TIMEOUT)

    def upload_certificate(self, cert_id: int, files: dict) -> dict:
        return self.post(f"/nginx/certificates/{cert_id}/upload", files=files)

    def download_certificate(self, cert_id: int) -> requests.Response:
        return self.get(f"/nginx/certificates/{cert_id}/download", raw=True)

    # --- users --------------------------------------------------------------

    def set_user_password(self, user_id: int, secret: str, current: Optional[str] = None) -> Any:
        payload = {"type": "password", "secret": secret}
        if current is not None:
            payload["current"] = current
        return self.put(f"/users/{user_id}/auth", json=payload)

    # --- misc ---------------------------------------------------------------

    def host_report(self) -> dict:
        return self.get("/reports/hosts")

    def audit_log(self) -> list:
        return self.get("/audit-log", params={"expand": "user"})

    def settings(self) -> list:
        return self.get("/settings")


def _error_message(response: requests.Response) -> str:
    try:
        body = response.json()
        message = body["error"]["message"]
    except (ValueError, KeyError, TypeError):
        message = response.text.strip() or response.reason
    return f"{response.status_code} {response.reason}: {message}"
