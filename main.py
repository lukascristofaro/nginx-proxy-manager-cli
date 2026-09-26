from connection import Connection

conn = Connection('192.168.1.210', 81)
token = conn.get_token('api@homelab.lan', '2tizjilp3rU6aG5o')
print(conn.decode_jwt_payload(token))