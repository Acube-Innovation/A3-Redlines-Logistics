# Copyright (c) 2026, Acube and contributors
# For license information, please see license.txt
"""
Whitelisted orchestration API for a3_logistics.

a3_webconsole keeps owning the UI and calls these exactly as it already calls
a3_trip_management / a3_warehouse_management whitelisted methods. Each create/update writes the
service doctype, then performs EXACTLY ONE foreground Opportunity.save() — that single save
triggers the stacked validate handler which folds the new charges into opportunity_line_item.
This is the only place an Opportunity.save() originates for these verticals.
"""

import json

import frappe
from frappe import _

# Booking-type label -> A3 Logistics Settings check fieldname. Labels match the tiles on
# a3_webconsole's create_booking/booking_type page.
BOOKING_TYPE_FLAGS = {
	"Transport": "enable_transport",
	"Warehousing": "enable_warehousing",
	"3PL Logistics & Distribution": "enable_3pl",
	"Air Shipping": "enable_air_shipping",
	"Sea Shipping": "enable_sea_shipping",
	"Customs Clearance": "enable_customs_clearance",
	"Industrial Packing": "enable_industrial_packing",
	"Packing & Relocation": "enable_packing_relocation",
}

# When a flag was never set on the Single (e.g. right after adding the field), fall back to these
# so the existing, already-live services never turn "Under Construction" by accident.
_ENABLE_DEFAULTS = {"enable_transport": 1, "enable_warehousing": 1}


# @frappe.whitelist()
# def get_enabled_booking_types():
# 	"""Map of booking-type label -> 1/0, driven by A3 Logistics Settings check fields.

# 	The booking-type selection page reads this to decide which tiles are live vs. Under Construction.
# 	"""
# 	try:
# 		s = frappe.get_cached_doc("A3 Logistics Settings")
# 	except Exception:
# 		s = None
# 	out = {}
# 	for label, field in BOOKING_TYPE_FLAGS.items():
# 		val = s.get(field) if s else None
# 		if val is None:
# 			val = _ENABLE_DEFAULTS.get(field, 0)
# 		out[label] = int(val or 0)
# 	return out


def _payload(payload):
	if isinstance(payload, str):
		return json.loads(payload or "{}")
	return payload or {}


def _require_opportunity(opportunity):
	if not opportunity or not frappe.db.exists("Opportunity", opportunity):
		frappe.throw(_("Valid Opportunity is required"))


def _upsert(doctype, opportunity, payload):
	"""Create or update a service doc. Updates when payload carries an existing `name`."""
	data = _payload(payload)
	name = data.pop("name", None)
	if name and frappe.db.exists(doctype, name):
		doc = frappe.get_doc(doctype, name)
	else:
		doc = frappe.new_doc(doctype)
	doc.opportunity = opportunity
	doc.update(data)
	doc.save(ignore_permissions=True)
	return doc


def _refresh_opportunity(opportunity):
	"""The single foreground save that re-derives opportunity_line_item via the stacked hook."""
	opp = frappe.get_doc("Opportunity", opportunity)
	opp.save(ignore_permissions=True)
	return opp.name


def _create_service(doctype, opportunity, payload):
	_require_opportunity(opportunity)
	doc = _upsert(doctype, opportunity, payload)
	_refresh_opportunity(opportunity)
	return {"name": doc.name, "opportunity": opportunity}


# --------------------------------------------------------------------------------------
# Service create / update endpoints
# --------------------------------------------------------------------------------------
@frappe.whitelist()
def create_air_shipment(opportunity, payload=None):
	return _create_service("Air Shipment Details", opportunity, payload)


@frappe.whitelist()
def create_sea_shipment(opportunity, payload=None):
	return _create_service("Sea Shipment Details", opportunity, payload)


@frappe.whitelist()
def create_customs_clearance(opportunity, payload=None):
	return _create_service("Customs Clearance Details", opportunity, payload)


@frappe.whitelist()
def create_packing_specification(opportunity, payload=None):
	return _create_service("Packing Specification", opportunity, payload)


@frappe.whitelist()
def create_relocation(opportunity, payload=None):
	return _create_service("Relocation Details", opportunity, payload)


@frappe.whitelist()
def create_tpl_contract(opportunity, payload=None):
	return _create_service("TPL Vendor Contract", opportunity, payload)


@frappe.whitelist()
def record_tpl_inbound(opportunity, payload=None):
	return _create_service("TPL Inbound Order", opportunity, payload)


@frappe.whitelist()
def record_tpl_outbound(opportunity, payload=None):
	return _create_service("TPL Outbound Order", opportunity, payload)


# --------------------------------------------------------------------------------------
# Read-only helpers (rate lookup + readback)
# --------------------------------------------------------------------------------------
@frappe.whitelist()
def get_air_freight_rate(origin_airport=None, destination_airport=None, airline=None, cargo_type=None):
	filters = {"is_active": 1}
	if origin_airport:
		filters["origin_airport"] = origin_airport
	if destination_airport:
		filters["destination_airport"] = destination_airport
	if airline:
		filters["airline"] = airline
	if cargo_type:
		filters["cargo_type"] = cargo_type
	rows = frappe.get_all(
		"Air Freight Tariff",
		filters=filters,
		fields=["name", "rate_basis", "rate_per_kg", "rate_per_cbm", "min_charge", "charge_item"],
		limit=1,
	)
	return rows[0] if rows else None


@frappe.whitelist()
def get_sea_freight_rate(origin_port=None, destination_port=None, shipping_line=None, container_type=None, shipment_mode=None):
	filters = {"is_active": 1}
	for key, val in (
		("origin_port", origin_port),
		("destination_port", destination_port),
		("shipping_line", shipping_line),
		("container_type", container_type),
		("shipment_mode", shipment_mode),
	):
		if val:
			filters[key] = val
	rows = frappe.get_all(
		"Sea Freight Tariff",
		filters=filters,
		fields=["name", "rate_per_container", "rate_per_cbm", "min_charge", "charge_item"],
		limit=1,
	)
	return rows[0] if rows else None


@frappe.whitelist()
def get_logistics_summary(opportunity):
	"""All logistics docs + their derived charge rows for the booking-confirmation readback."""
	_require_opportunity(opportunity)
	from a3_logistics.events.opportunity import collect_logistics_rows

	doctypes = [
		"Air Shipment Details",
		"Sea Shipment Details",
		"Customs Clearance Details",
		"Packing Specification",
		"Relocation Details",
		"TPL Vendor Contract",
		"TPL Inbound Order",
		"TPL Outbound Order",
	]
	docs = {}
	for dt in doctypes:
		names = frappe.get_all(dt, filters={"opportunity": opportunity}, pluck="name")
		if names:
			docs[dt] = names
	return {
		"opportunity": opportunity,
		"documents": docs,
		"charge_rows": collect_logistics_rows(opportunity),
	}
