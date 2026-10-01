from connection import Connection
from requestApi import RequestApi
import argparse

class main:
    def __init__(self):
        self.conn = Connection('192.168.1.210', 81)
        self.token = self.conn.get_token('api@homelab.lan', '2tizjilp3rU6aG5o')

    def show_proxy_hosts(self):
        proxy_host = RequestApi(f'http://{self.conn.host}:{self.conn.port}', self.token)
        print(proxy_host.get_response().json())

    def create_proxy_host(self, domain, forward_host, forward_port, protocol):
        proxy_host = RequestApi(f'http://{self.conn.host}:{self.conn.port}', self.token)
        print(proxy_host.create_proxy_host(self.token, domain, forward_host, forward_port, protocol))

    def run(self):
        parser = argparse.ArgumentParser(description="Manage Nginx Proxy Manager")
        parser.add_argument("command", choices=["show", "create"], help="Command to execute")
        parser.add_argument("--domain", help="Domain name")
        parser.add_argument("--forward-host", help="Forward host")
        parser.add_argument("--forward-port", type=int, help="Forward port")
        parser.add_argument("--protocol", help="Forward protocol")

        args = parser.parse_args()

        if args.command == "show":
            self.show_proxy_hosts()
        elif args.command == "create":
            if not all([args.domain, args.forward_host, args.forward_port, args.protocol]):
                print("Error: All arguments (--domain, --forward-host, --forward-port, --protocol) are required for the 'create' command.")
            else:
                self.create_proxy_host(args.domain, args.forward_host, args.forward_port, args.protocol)

if __name__ == "__main__":
    app = main()
    app.run()