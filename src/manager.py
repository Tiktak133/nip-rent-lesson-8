"""Manager module for rental operations and settlement reporting."""

from datetime import datetime
from typing import List

from src.models import (
    Apartment,
    ApartmentEvent,
    ApartmentSettlement,
    Bill,
    Parameters,
    Tenant,
    TenantBlacklistEntry,
    TenantSettlement,
    Transfer,
)


class Manager:
    """Business logic for rental management, settlements, and reporting."""

    def __init__(self, parameters: Parameters):
        """Initialize the manager and load core application data."""
        self.parameters = parameters

        self.apartments = {}
        self.tenants = {}
        self.transfers = []
        self.bills = []
        self.tenants_blacklist = []
        self.apartment_events = []

        self.load_data()

    def load_data(self):
        """Load core JSON data for apartments, tenants, transfers, bills, and blacklist."""
        self.apartments = Apartment.from_json_file(self.parameters.apartments_json_path)
        self.tenants = Tenant.from_json_file(self.parameters.tenants_json_path)
        self.transfers = Transfer.from_json_file(self.parameters.transfers_json_path)
        self.bills = Bill.from_json_file(self.parameters.bills_json_path)
        self.tenants_blacklist = TenantBlacklistEntry.from_json_file(self.parameters.tenants_blacklist_json_path)

    def load_additional_data(self):
        """Load supplementary apartment event data from the JSON file."""
        self.apartment_events = ApartmentEvent.from_json_file(self.parameters.apartment_events_json_path)

    def generate_apartment_events_report(
        self,
        apartment_key: str,
        only_unsolved: bool = True,
    ) -> List[ApartmentEvent]:
        """Return reported apartment events, optionally filtering only unsolved ones."""
        if apartment_key not in self.apartments:
            raise ValueError("Apartment key does not exist")
        return [
            event
            for event in self.apartment_events
            if event.apartment == apartment_key and (not event.solved or not only_unsolved)
        ]

    def check_tenants_apartment_keys(self) -> bool:
        """Validate that every tenant is assigned to a known apartment."""
        for tenant in self.tenants.values():
            if tenant.apartment not in self.apartments:
                return False
        return True
    
    def get_apartment(self, apartment_key: str) -> Apartment | None:
        """Return the apartment object for the given key, or None if not found."""
        return self.apartments.get(apartment_key, None)

    def get_apartment_costs(
        self,
        apartment_key: str,
        year: int | None = None,
        month: int | None = None,
    ) -> float | None:
        """Return the total bill amount for the apartment filtered by year and month."""
        if month is not None and (month < 1 or month > 12):
            raise ValueError("Month must be between 1 and 12")
        if apartment_key not in self.apartments:
            return None
        total_cost = 0.0
        for bill in self.bills:
            if (
                bill.apartment == apartment_key
                and (year is None or bill.settlement_year == year)
                and (month is None or bill.settlement_month == month)
            ):
                total_cost += bill.amount_pln
        return total_cost

    def get_settlement(self, apartment_key: str, year: int, month: int) -> ApartmentSettlement | None:
        """Construct an apartment settlement for the given period, if apartment exists."""
        if month < 1 or month > 12:
            raise ValueError("Month must be between 1 and 12")
        if apartment_key not in self.apartments:
            return None
        total_cost = self.get_apartment_costs(apartment_key, year, month)
        if total_cost is None:
            return None

        return ApartmentSettlement(
            key=f"{apartment_key}-{year}-{month}",
            apartment=apartment_key,
            year=year,
            month=month,
            total_due_pln=total_cost
        )
    
    def create_tenants_settlements(
        self,
        apartment_settlement: ApartmentSettlement,
    ) -> List[TenantSettlement] | None:
        """Create a settlement record for each tenant in the apartment."""
        if apartment_settlement.month < 1 or apartment_settlement.month > 12:
            raise ValueError("Month must be between 1 and 12")
        if apartment_settlement.apartment not in self.apartments:
            return None
        tenants_in_apartment = [
            tenant
            for tenant in self.tenants.values()
            if tenant.apartment == apartment_settlement.apartment
        ]
        if not tenants_in_apartment:
            return []

        return [
            TenantSettlement(
                tenant=tenant.name,
                apartment_settlement=apartment_settlement.key,
                month=apartment_settlement.month,
                year=apartment_settlement.year,
                total_due_pln=apartment_settlement.total_due_pln / len(tenants_in_apartment),
            )
            for tenant in tenants_in_apartment
        ]
    
    def get_debtors(self, apartment_key: str, year: int, month: int) -> List[str]:
        """Return tenant names who have paid less than their share for a settlement."""
        if month < 1 or month > 12:
            raise ValueError("Month must be between 1 and 12")
        settlement = self.get_settlement(apartment_key, year, month)
        if settlement is None:
            return []

        output = []
        tenant_settlements = self.create_tenants_settlements(settlement)

        for tenant_settlement in tenant_settlements:
            total_paid = 0.0
            for transfer in self.transfers:
                tenant = self.tenants.get(transfer.tenant)
                if tenant is None:
                    continue
                if (
                    tenant.name == tenant_settlement.tenant
                    and transfer.settlement_year == year
                    and transfer.settlement_month == month
                ):
                    total_paid += transfer.amount_pln
            if total_paid < tenant_settlement.total_due_pln:
                output.append(tenant_settlement.tenant)
        return output
    
    def calculate_tax(self, year: int, month: int, tax_rate: float) -> float:
        """Calculate tax due for transfers in a settlement period."""
        total_income = sum(
            transfer.amount_pln
            for transfer in self.transfers
            if transfer.settlement_year == year and transfer.settlement_month == month
        )
        return round(total_income * tax_rate, 0)
    
    def check_deposits(self) -> float:
        """Return the difference between actual deposits received and deposits due."""
        total_deposits = 0.0
        total_due = 0.0
        for tenant in self.tenants.values():
            for transfer in self.transfers:
                transfer_tenant = self.tenants.get(transfer.tenant)
                if (
                    transfer_tenant is not None
                    and transfer_tenant.name == tenant.name
                    and transfer.transfer_type == 'deposit'
                ):
                    total_deposits += transfer.amount_pln
            total_due += tenant.deposit_pln

        return total_deposits - total_due
    
    def get_annual_balance(self, year: int) -> float:
        """Calculate the annual balance for a given year.

        Args:
            year (int): Year for which to calculate the balance.

        Returns:
            float: Difference between total income from transfers and total due from bills for the year.
        """
        total_income = sum(
            transfer.amount_pln
            for transfer in self.transfers
            if transfer.settlement_year == year
        )
        total_due = sum(
            bill.amount_pln
            for bill in self.bills
            if bill.settlement_year == year
        )
        return total_income - total_due
    
    def has_any_bills(self, apartment_key: str, year: int, month: int) -> bool:
        """Check whether there are bills for a given apartment in a settlement period."""
        if month < 1 or month > 12:
            raise ValueError("Month must be between 1 and 12")
        if apartment_key not in self.apartments:
            raise ValueError("Apartment key does not exist")
        return any(
            bill
            for bill in self.bills
            if bill.apartment == apartment_key
            and bill.settlement_year == year
            and bill.settlement_month == month
        )
    
    def check_transfers_amount_range(self) -> bool:
        """Verify that transfer amounts stay within allowed deposit and refund limits."""
        for transfer in self.transfers:
            if (
                transfer.amount_pln > self.parameters.max_transfer_pln
                or transfer.amount_pln < -self.parameters.max_refund_pln
            ):
                return False
        return True
    
    def check_tenant_blacklist(self, tenant_name: str) -> bool:
        """Return True if a tenant is present in the blacklist."""
        return any(entry for entry in self.tenants_blacklist if entry.tenant == tenant_name)
    
    def check_transfers_tenant(self) -> bool:
        """Validate that transfers refer to active tenants within agreement years."""
        for transfer in self.transfers:
            tenant = self.tenants.get(transfer.tenant)
            if tenant is None:
                return False
            if transfer.settlement_year is not None and transfer.settlement_month is not None:
                agreement_from = datetime.strptime(tenant.date_agreement_from, "%Y-%m-%d").date()
                agreement_to = datetime.strptime(tenant.date_agreement_to, "%Y-%m-%d").date()
                if transfer.settlement_year < agreement_from.year or transfer.settlement_year > agreement_to.year:
                    return False

        return True