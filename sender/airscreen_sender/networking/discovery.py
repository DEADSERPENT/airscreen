"""mDNS / DNS-SD discovery of AirScreen receivers (_airscreen._tcp.local). Discovery is not authentication."""
from __future__ import annotations

import time
from dataclasses import dataclass

from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

SERVICE = "_airscreen._tcp.local."


@dataclass(frozen=True)
class Receiver:
    name: str
    ip: str
    port: int
    receiver_id: str


class _Collector(ServiceListener):
    def __init__(self, zc: Zeroconf) -> None:
        self.zc = zc
        self.found: dict[str, Receiver] = {}

    def add_service(self, zc, type_, name):
        info = zc.get_service_info(type_, name, timeout=2000)
        if not info:
            return
        addrs = info.parsed_addresses()
        v4 = [a for a in addrs if ":" not in a]
        if not v4:
            return
        props = {k.decode(): (v.decode() if v else "") for k, v in info.properties.items()}
        self.found[name] = Receiver(props.get("name") or name.split(".")[0], v4[0], info.port, props.get("id", ""))

    def update_service(self, zc, type_, name):
        self.add_service(zc, type_, name)

    def remove_service(self, zc, type_, name):
        self.found.pop(name, None)


def discover(timeout: float = 3.0) -> list[Receiver]:
    zc = Zeroconf()
    try:
        collector = _Collector(zc)
        browser = ServiceBrowser(zc, SERVICE, collector)
        time.sleep(timeout)
        browser.cancel()
        return sorted(collector.found.values(), key=lambda r: r.name)
    finally:
        zc.close()
