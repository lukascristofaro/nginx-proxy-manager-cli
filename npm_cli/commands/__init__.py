from . import access_lists, auth, certificates, hosts, system, users

MODULES = (auth, hosts, certificates, access_lists, users, system)


def register_all(root) -> None:
    for module in MODULES:
        module.register(root)
