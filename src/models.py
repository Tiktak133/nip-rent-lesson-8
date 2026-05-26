"""Data models for the rental management application."""

import json
from typing import Dict, List

from pydantic import BaseModel, Field


class Parameters(BaseModel):
    """Application settings and default file paths."""

    apartments_json_path: str = 'data/apartments.json'
    tenants_json_path: str = 'data/tenants.json'
    transfers_json_path: str = 'data/transfers.json'
    bills_json_path: str = 'data/bills.json'
    tenants_blacklist_json_path: str = 'data/tenants_blacklist.json'
    apartment_events_json_path: str = 'data/apartment_events.json'

    max_transfer_pln: float = 4500.0
    max_refund_pln: float = 2500.0


class Room(BaseModel):
    """A single room within an apartment."""

    name: str
    area_m2: float


class Apartment(BaseModel):
    """Apartment metadata and room layout."""

    key: str
    name: str
    location: str
    area_m2: float
    rooms: Dict[str, Room]

    @staticmethod
    def from_json_file(file_path: str) -> Dict[str, 'Apartment']:
        """Load apartments from a JSON file into a keyed dictionary."""
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("Expected a dictionary of apartments")
        return {key: Apartment(**apartment) for key, apartment in data.items()}


class Tenant(BaseModel):
    """Tenant details and rental agreement dates."""

    name: str
    apartment: str
    room: str
    rent_pln: float
    deposit_pln: float
    date_agreement_from: str
    date_agreement_to: str

    @staticmethod
    def from_json_file(file_path: str) -> Dict[str, 'Tenant']:
        """Load tenants from a JSON file into a keyed dictionary."""
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("Expected a dictionary of tenants")
        return {key: Tenant(**tenant) for key, tenant in data.items()}


class TenantBlacklistEntry(BaseModel):
    """Entry representing a blacklisted tenant."""

    tenant: str
    reason: str

    @staticmethod
    def from_json_file(file_path: str) -> List['TenantBlacklistEntry']:
        """Load tenant blacklist entries from a JSON file."""
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError("Expected a list of blacklist entries")
        return [TenantBlacklistEntry(**entry) for entry in data]


class Transfer(BaseModel):
    """Transfer record for a tenant settlement."""

    amount_pln: float
    date: str
    settlement_year: int | None
    settlement_month: int | None
    tenant: str
    transfer_type: str | None = Field(default=None, alias='type')

    @staticmethod
    def from_json_file(file_path: str) -> List['Transfer']:
        """Load transfer records from a JSON file."""
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError("Expected a list of transfers")
        return [Transfer(**transfer) for transfer in data]


class Bill(BaseModel):
    """Bill record for apartment settlements."""

    amount_pln: float
    date_due: str
    apartment: str
    settlement_year: int
    settlement_month: int
    bill_type: str = Field(alias='type')

    @staticmethod
    def from_json_file(file_path: str) -> List['Bill']:
        """Load bill records from a JSON file."""
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError("Expected a list of bills")
        return [Bill(**bill) for bill in data]


class ApartmentSettlement(BaseModel):
    """Summary of apartment costs for a settlement period."""

    key: str
    apartment: str
    month: int
    year: int
    total_due_pln: float
    total_transfers_pln: float = 0.0
    balance_pln: float = 0.0


class TenantSettlement(BaseModel):
    """Tenant-level allocation for an apartment settlement."""

    tenant: str
    apartment_settlement: str
    month: int
    year: int
    total_due_pln: float
    total_transfers_pln: float = 0.0
    balance_pln: float = 0.0


class ApartmentEvent(BaseModel):
    """Reported event associated with an apartment."""

    date: str
    apartment: str
    amount_pln: float | None = None
    tenant: str | None = None
    description: str
    solved: bool = False

    @staticmethod
    def from_json_file(file_path: str) -> List['ApartmentEvent']:
        """Load apartment event records from a JSON file."""
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError("Expected a list of apartment events")
        return [ApartmentEvent(**event) for event in data]
