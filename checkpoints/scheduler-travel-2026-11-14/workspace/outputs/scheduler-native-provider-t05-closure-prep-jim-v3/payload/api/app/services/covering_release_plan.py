"""Uninstalled production plan; construct fresh resources on each HTTP worker."""
from dataclasses import dataclass
from typing import Callable

from app.services.covering_native_checkout import PostgreSQLPeer
from app.services.covering_native_orm_factory import NativeORMFactories, NativeRuntimePins
from app.services.covering_transport_policy import ProviderCounter, approved_provider_limits
from app.services.covering_http_transport import CoveringHTTP
from app.services.covering_domain_adapters import make_domain_ports


@dataclass(frozen=True)
class CoveringReleasePlan:
    database_profile: PostgreSQLPeer
    password_supplier: Callable
    runtime_pins: NativeRuntimePins
    provider_routes: tuple
    settings: object

    def for_request(self, budget):
        # No connection is opened here. Factories are called only AFTER role
        # reservation by the request's joined connector.
        from app.services.covering_http_dispatch import CoveringReleaseBinding
        factories=NativeORMFactories(profile=self.database_profile,
            password_supplier=self.password_supplier,runtime_pins=self.runtime_pins)
        counter=ProviderCounter(approved_provider_limits(),budget.work_remaining)
        transport=CoveringHTTP(counter=counter,routes=self.provider_routes)
        return CoveringReleaseBinding(
            parent_factory=factories.parent_factory,
            session_factory=factories.session_factory,
            domain_ports=make_domain_ports(settings=self.settings,transport=transport))

