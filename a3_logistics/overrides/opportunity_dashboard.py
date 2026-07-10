# Copyright (c) 2026, Acube and contributors
# For license information, please see license.txt
"""Additive Opportunity dashboard override.

MERGE only — append a "Logistics" group and merge non_standard_fieldnames. Never replaces the
incoming `data`, so a3_trip_management and a3_warehouse_management dashboard sections survive.
a3_logistics loads last, so `data` already carries the other apps' contributions.
"""

LOGISTICS_TRANSACTIONS = [
	"Air Shipment Details",
	"Sea Shipment Details",
	"Customs Clearance Details",
	"Packing Specification",
	"Relocation Details",
	"TPL Vendor Contract",
	"TPL Inbound Order",
	"TPL Outbound Order",
]


def get_data(data=None):
	if data is None:
		data = {"transactions": [], "non_standard_fieldnames": {}}
	data.setdefault("transactions", [])
	data.setdefault("non_standard_fieldnames", {})

	# Every logistics top-level doctype links to Opportunity via the `opportunity` field.
	for doctype in LOGISTICS_TRANSACTIONS:
		data["non_standard_fieldnames"][doctype] = "opportunity"

	data["transactions"].append(
		{
			"label": "Logistics",
			"items": LOGISTICS_TRANSACTIONS,
		}
	)
	return data
