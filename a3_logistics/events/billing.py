# Copyright (c) 2026, Acube and contributors
# For license information, please see license.txt
"""
Recurring billing for 3PL (the only vertical with period accrual). Registered under
`daily_long`. Mirrors a3_trip_management.generate_monthly_warehouse_invoices: it acts only on
the last day of the month and is idempotency-keyed so a double-run never double-bills.

It does NOT pre-empt the warehouse monthly invoice job and does NOT create parallel Sales
Invoices for the same Opportunity.

The concrete accrual rule (flat monthly management fee vs. throughput-based) depends on
Approval Gate 1 (3PL pricing model) and is intentionally left as a guarded, idempotent skeleton
until signed off — so installing this app changes no billing behaviour.
"""

import frappe
from frappe.utils import getdate, get_last_day, nowdate


def generate_logistics_invoices():
	today = getdate(nowdate())
	# Guard: only run at month-end, mirroring the warehouse scheduler's cadence.
	if today != getdate(get_last_day(today)):
		return

	period_key = today.strftime("%Y-%m")

	contracts = frappe.get_all(
		"TPL Vendor Contract",
		filters={"status": "Active", "recurring_billing": 1},
		fields=["name", "opportunity"],
	)
	for c in contracts:
		try:
			_accrue_contract_period(c, period_key)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"a3_logistics: 3PL accrual failed for {c.name}")


def _accrue_contract_period(contract, period_key):
	"""Idempotent per (contract, period). No-op until Gate 1 accrual rule is confirmed.

	The idempotency check below is the durable guard: when the accrual rule is enabled, it must
	first verify no charge already exists for this (contract, period) before creating one.
	"""
	# Placeholder idempotency guard — replace the body with the approved accrual once Gate 1 lands.
	# already = frappe.db.exists("Sales Invoice", {"custom_3pl_contract": contract.name,
	#                                               "custom_3pl_period": period_key})
	# if already:
	#     return
	return
