import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from npm_cli import config
from npm_cli.cli import main

URL = "http://npm.test:81"


class FakeResponse:
    def __init__(self, status=200, body=None, reason="OK"):
        self.status_code = status
        self.ok = status < 400
        self.reason = reason
        self._body = body
        self.content = b"" if body is None else json.dumps(body).encode()
        self.text = self.content.decode()

    def json(self):
        if self._body is None:
            raise ValueError("no body")
        return self._body


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        env = {"NPM_CLI_CONFIG_DIR": self.tmp.name}
        self.env = mock.patch.dict(os.environ, env)
        self.env.start()
        for var in ("NPM_URL", "NPM_TOKEN", "NPM_EMAIL", "NPM_PASSWORD"):
            os.environ.pop(var, None)

        self.calls = []
        self.routes = {}
        patcher = mock.patch("requests.Session.request", side_effect=self._fake_request)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def _fake_request(self, method, url, **kwargs):
        path = url[len(URL):]
        self.calls.append((method, path, kwargs))
        return self.routes.get((method, path), FakeResponse(404, {"error": {"message": "Not Found"}}, "Not Found"))

    def logged_in(self, expires_in=timedelta(days=1)):
        expires = (datetime.now(timezone.utc) + expires_in).isoformat()
        config.save({"url": URL, "token": "tok", "expires": expires, "email": "a@b.c"})

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()


class TestAuth(CliTestCase):
    def test_login_saves_session(self):
        self.routes[("POST", "/api/tokens")] = FakeResponse(body={"token": "abc", "expires": "2030-01-01T00:00:00.000Z"})
        self.routes[("GET", "/api/users/me")] = FakeResponse(body={"name": "Admin", "email": "a@b.c"})

        code, out, _ = self.run_cli("login", "--url", "npm.test:81/", "-e", "a@b.c", "-p", "secret")

        self.assertEqual(code, 0)
        self.assertIn("Logged in", out)
        saved = config.load()
        self.assertEqual(saved["url"], URL)
        self.assertEqual(saved["token"], "abc")
        self.assertNotIn("password", json.dumps(saved))

    def test_not_logged_in(self):
        code, _, err = self.run_cli("proxy", "list", "--url", URL)
        self.assertEqual(code, 1)
        self.assertIn("Not logged in", err)

    def test_expired_token_relogs_with_env_credentials(self):
        self.logged_in(expires_in=timedelta(hours=-1))
        os.environ.update(NPM_EMAIL="a@b.c", NPM_PASSWORD="pw")
        self.routes[("POST", "/api/tokens")] = FakeResponse(body={"token": "new", "expires": "2030-01-01T00:00:00Z"})
        self.routes[("GET", "/api/nginx/proxy-hosts")] = FakeResponse(body=[])

        code, _, _ = self.run_cli("proxy", "list")

        self.assertEqual(code, 0)
        self.assertEqual(config.load()["token"], "new")

    def test_token_close_to_expiry_is_refreshed(self):
        self.logged_in(expires_in=timedelta(hours=1))
        self.routes[("GET", "/api/tokens")] = FakeResponse(body={"token": "refreshed", "expires": "2030-01-01T00:00:00Z"})
        self.routes[("GET", "/api/nginx/proxy-hosts")] = FakeResponse(body=[])

        self.assertEqual(self.run_cli("proxy", "list")[0], 0)
        self.assertEqual(config.load()["token"], "refreshed")


class TestProxyHosts(CliTestCase):
    def setUp(self):
        super().setUp()
        self.logged_in()

    def test_list_table(self):
        self.routes[("GET", "/api/nginx/proxy-hosts")] = FakeResponse(body=[
            {"id": 1, "domain_names": ["a.example.com"], "forward_scheme": "http", "forward_host": "10.0.0.1",
             "forward_port": 80, "certificate_id": 2, "ssl_forced": True, "enabled": True, "meta": {}},
        ])
        code, out, _ = self.run_cli("proxy", "list")
        self.assertEqual(code, 0)
        self.assertIn("a.example.com", out)
        self.assertIn("http://10.0.0.1:80", out)
        self.assertIn("forced", out)
        method, path, kwargs = self.calls[0]
        self.assertEqual(kwargs["params"]["expand"], "owner,certificate,access_list")

    def test_list_json_flag_before_or_after(self):
        self.routes[("GET", "/api/nginx/proxy-hosts")] = FakeResponse(body=[{"id": 1}])
        for argv in (("--json", "proxy", "list"), ("proxy", "list", "--json")):
            code, out, _ = self.run_cli(*argv)
            self.assertEqual(json.loads(out), [{"id": 1}])

    def test_create_payload(self):
        self.routes[("POST", "/api/nginx/proxy-hosts")] = FakeResponse(body={"id": 7, "domain_names": ["a.com"]})
        code, out, _ = self.run_cli("proxy", "create", "-d", "a.com", "-d", "b.com",
                                    "--forward-host", "10.0.0.5", "--forward-port", "8080", "--no-websockets")
        self.assertEqual(code, 0)
        self.assertIn("Created proxy host #7", out)
        payload = self.calls[-1][2]["json"]
        self.assertEqual(payload["domain_names"], ["a.com", "b.com"])
        self.assertEqual(payload["forward_port"], 8080)
        self.assertEqual(payload["forward_scheme"], "http")
        self.assertFalse(payload["allow_websocket_upgrade"])
        self.assertTrue(payload["block_exploits"])

    def test_create_with_ssl_requests_certificate_first(self):
        self.routes[("POST", "/api/nginx/certificates")] = FakeResponse(body={"id": 42})
        self.routes[("POST", "/api/nginx/proxy-hosts")] = FakeResponse(body={"id": 8})
        code, _, _ = self.run_cli("proxy", "create", "-d", "a.com", "--forward-host", "h", "--forward-port", "1",
                                  "--ssl", "--email", "me@a.com", "--force-ssl")
        self.assertEqual(code, 0)
        cert_payload = self.calls[0][2]["json"]
        self.assertEqual(cert_payload["domain_names"], ["a.com"])
        self.assertEqual(cert_payload["meta"]["letsencrypt_email"], "me@a.com")
        host_payload = self.calls[1][2]["json"]
        self.assertEqual(host_payload["certificate_id"], 42)
        self.assertTrue(host_payload["ssl_forced"])

    def test_update_sends_only_given_fields(self):
        self.routes[("PUT", "/api/nginx/proxy-hosts/3")] = FakeResponse(body={"id": 3})
        code, _, _ = self.run_cli("proxy", "update", "3", "--forward-port", "9000", "--http2")
        self.assertEqual(code, 0)
        self.assertEqual(self.calls[-1][2]["json"], {"forward_port": 9000, "http2_support": True})

    def test_update_without_options_fails(self):
        code, _, err = self.run_cli("proxy", "update", "3")
        self.assertEqual(code, 1)
        self.assertIn("Nothing to update", err)

    def test_delete_requires_yes_when_not_interactive(self):
        with mock.patch("sys.stdin.isatty", return_value=False):
            code, _, err = self.run_cli("proxy", "delete", "3")
        self.assertEqual(code, 1)
        self.assertIn("--yes", err)

    def test_delete_and_disable(self):
        self.routes[("DELETE", "/api/nginx/proxy-hosts/3")] = FakeResponse(body=True)
        self.routes[("POST", "/api/nginx/proxy-hosts/4/disable")] = FakeResponse(body=True)
        self.assertEqual(self.run_cli("proxy", "rm", "3", "-y")[0], 0)
        self.assertEqual(self.run_cli("proxy", "disable", "4")[0], 0)

    def test_api_error_message(self):
        self.routes[("POST", "/api/nginx/proxy-hosts")] = FakeResponse(
            400, {"error": {"code": 400, "message": "a.com is already in use"}}, "Bad Request")
        code, _, err = self.run_cli("proxy", "create", "-d", "a.com", "--forward-host", "h", "--forward-port", "1")
        self.assertEqual(code, 1)
        self.assertIn("a.com is already in use", err)


class TestOtherResources(CliTestCase):
    def setUp(self):
        super().setUp()
        self.logged_in()

    def test_stream_create(self):
        self.routes[("POST", "/api/nginx/streams")] = FakeResponse(body={"id": 1})
        code, _, _ = self.run_cli("stream", "create", "--incoming-port", "2222",
                                  "--forward-host", "10.0.0.2", "--forward-port", "22")
        self.assertEqual(code, 0)
        payload = self.calls[-1][2]["json"]
        self.assertEqual(payload["forwarding_host"], "10.0.0.2")
        self.assertTrue(payload["tcp_forwarding"])
        self.assertFalse(payload["udp_forwarding"])

    def test_redirect_create(self):
        self.routes[("POST", "/api/nginx/redirection-hosts")] = FakeResponse(body={"id": 1})
        code, _, _ = self.run_cli("redirect", "create", "-d", "old.com", "--to", "new.com", "--code", "302")
        self.assertEqual(code, 0)
        payload = self.calls[-1][2]["json"]
        self.assertEqual(payload["forward_domain_name"], "new.com")
        self.assertEqual(payload["forward_http_code"], 302)

    def test_access_list_create(self):
        self.routes[("POST", "/api/nginx/access-lists")] = FakeResponse(body={"id": 1, "name": "lan"})
        code, _, _ = self.run_cli("acl", "create", "--name", "lan", "--user", "bob:pw",
                                  "--allow", "192.168.0.0/16", "--deny", "all")
        self.assertEqual(code, 0)
        payload = self.calls[-1][2]["json"]
        self.assertEqual(payload["items"], [{"username": "bob", "password": "pw"}])
        self.assertEqual(payload["clients"][1], {"address": "all", "directive": "deny"})

    def test_report(self):
        self.routes[("GET", "/api/reports/hosts")] = FakeResponse(body={"proxy": 3, "redirection": 1})
        code, out, _ = self.run_cli("report")
        self.assertEqual(code, 0)
        self.assertIn("proxy", out)


if __name__ == "__main__":
    unittest.main()
