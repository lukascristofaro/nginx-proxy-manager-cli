import requests

import base64
import json

class Connection:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def get_token(self, username, password):
        url = f'http://{self.host}:{self.port}/api/tokens'
        payload = {'identity': username, 'secret': password}
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return response.json()['token']
        else:
            raise Exception(f"Failed to get token: {response.status_code} - {response.text}")



    def decode_jwt_payload(self,token):
        payload = token.split(".")[1]

        payload += "=" * (-len(payload) % 4)

        return json.loads(
            base64.urlsafe_b64decode(payload)
        )