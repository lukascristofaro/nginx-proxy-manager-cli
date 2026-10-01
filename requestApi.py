
import requests


class RequestApi:
    def __init__(self, url, token):
        self.url = url
        self.token = token

    def get_response(self):
        headers = {
            "Authorization": f"Bearer {self.token}"
        }
        return requests.get(f"{self.url}/api/nginx/proxy-hosts", headers=headers)
    
    def post_response(self, data):
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        return requests.post(self.url, headers=headers, json=data)

    def create_proxy_host(self, token, domain, forward_host, forward_port, protocol):
        payload = {
            "domain_names": [domain],
            "forward_host": forward_host,
            "forward_port": forward_port,
            "forward_scheme": protocol,
            "access_list_id": None,
            "certificate_id": None,
            "ssl_forced": False,
            "caching_enabled": False,
            "block_exploits": True,
            "allow_websocket_upgrade": True,
            "http2_support": False,
            "hsts_enabled": False,
            "hsts_subdomains": False,
            "advanced_config": "",
            "meta": {}
        }

        response = requests.post(
            f"{self.url}/api/nginx/proxy-hosts",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            timeout=10
        )

        response.raise_for_status()

        return response.json()
    
    def create_letsencrypt_certificate(self, token, domain):
        payload = {
            "provider": "letsencrypt",
            "domain_names": [domain],
            "meta": {
                "dns_challenge": False
            }
        }

        response = requests.post(
            f"{self.url}/api/nginx/certificates",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            timeout=120
        )

        response.raise_for_status()

        return response.json()