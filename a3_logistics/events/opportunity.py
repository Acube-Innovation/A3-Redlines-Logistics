# Copyright (c) 2026, Acube and contributors
# For license information, please see license.txt
"""
Stacked Opportunity.validate handler for a3_logistics.

CONTRACT (see A3_LOGISTICS_ARCHITECTURE.md):
  * a3_trip_management's Opportunity.validate runs FIRST (it loads first in apps.txt). It may
    destructively rebuild `opportunity_line_item` (clear + re-append) and then computes VAT +
    payment_amount via calculate_total_charges().
  * a3_logistics loads LAST, so THIS handler runs AFTER all of trip's validate. It:
      1. derives logistics charge rows fresh from this app's service doctypes (never persisted),
      2. removes any stale logistics rows already in the table (idempotent rebuild — safe whether
         or not trip cleared the table this save),
      3. appends the freshly-derived rows,
      4. re-runs trip's calculate_total_charges() so logistics rows receive identical default
         tax template + VAT + payment_amount treatment.
  * It NEVER calls Opportunity.save() (avoids TimestampMismatchError) and never writes order_status.

Logistics rows are identified for idempotent rebuild by the Item group configured in
`A3 Logistics Settings` (default "Logistics Services"). Logistics charge Items MUST live in that
group and MUST NOT be shared with Transport/Warehouse rows, otherwise this handler would strip a
non-logistics row. after_install seeds the group + default Items accordingly.
"""

import frappe
from frappe.utils import cint, flt

DEFAULT_TAX_TEMPLATE = "UAE VAT 5% - RLI"
DEFAULT_ITEM_GROUP = "Logistics Services"

# booking_type string values handled natively by a3_trip_management — never managed here.
TRIP_NATIVE_BOOKING_TYPES = ("Transport", "Warehousing")


# --------------------------------------------------------------------------------------
# Settings / item-group helpers
# --------------------------------------------------------------------------------------
def _settings():
	"""Cached singleton; tolerant if the doctype isn't migrated yet."""
	try:
		return frappe.get_cached_doc("A3 Logistics Settings")
	except Exception:
		return None


def _logistics_item_group():
	s = _settings()
	group = getattr(s, "logistics_item_group", None) if s else None
	return group or DEFAULT_ITEM_GROUP


def get_logistics_charge_items():
	"""Set of Item codes that mark a row as logistics-owned (for idempotent removal)."""
	group = _logistics_item_group()
	try:
		items = frappe.get_all("Item", filters={"item_group": group}, pluck="name")
		return set(items)
	except Exception:
		return set()


def _default_tax_template(service_key=None):
	"""Per-service tax template override from settings, else the bench default."""
	s = _settings()
	if s and service_key:
		override = (s.get(f"{service_key}_tax_template") or "").strip()
		if override:
			return override
	return DEFAULT_TAX_TEMPLATE


def _line(item, qty, amount, rate, tax_template=None):
	"""Build one Opportunity Line Items row dict matching that child doctype's schema."""
	return {
		"item": item,
		"quantity": cint(qty) or 1,
		"amount": flt(amount),
		"average_rate": flt(rate if rate is not None else amount),
		"include_in_billing": 1,
		"status": "Pending",
		"tax_template": tax_template or "",
	}


# --------------------------------------------------------------------------------------
# Per-service row builders — each reads its own a3_logistics service docs for this Opportunity
# --------------------------------------------------------------------------------------
def _rows_air(opportunity):
	rows = []
	for d in frappe.get_all(
		"Air Shipment Details",
		filters={"opportunity": opportunity},
		fields=["name", "charge_item", "freight_amount"],
	):
		if flt(d.freight_amount) <= 0:
			continue
		item = d.charge_item or _service_default_item("air")
		if not item:
			continue
		rows.append(_line(item, 1, d.freight_amount, d.freight_amount, _default_tax_template("air")))
	return rows


def _rows_sea(opportunity):
	rows = []
	for d in frappe.get_all(
		"Sea Shipment Details",
		filters={"opportunity": opportunity},
		fields=["name", "charge_item", "freight_amount"],
	):
		if flt(d.freight_amount) <= 0:
			continue
		item = d.charge_item or _service_default_item("sea")
		if not item:
			continue
		rows.append(_line(item, 1, d.freight_amount, d.freight_amount, _default_tax_template("sea")))
	return rows


def _rows_from_child_charges(opportunity, parent_doctype, child_table_field, default_key):
	"""Generic: sum charge child rows (charge_item, quantity, rate, amount) into line items."""
	rows = []
	parents = frappe.get_all(parent_doctype, filters={"opportunity": opportunity}, pluck="name")
	for pname in parents:
		parent = frappe.get_doc(parent_doctype, pname)
		for c in parent.get(child_table_field) or []:
			amount = flt(c.get("amount")) or (flt(c.get("rate")) * (cint(c.get("quantity")) or 1))
			if amount <= 0:
				continue
			item = c.get("charge_item") or _service_default_item(default_key)
			if not item:
				continue
			tax = None
			# Customs statutory pass-through (duty/VAT disbursement) carries no extra VAT.
			if cint(c.get("is_pass_through")):
				tax = (_settings().get("pass_through_tax_template") if _settings() else "") or ""
			else:
				tax = _default_tax_template(default_key)
			rows.append(_line(item, c.get("quantity") or 1, amount, c.get("rate") or amount, tax))
	return rows


def _rows_customs(opportunity):
	return _rows_from_child_charges(opportunity, "Customs Clearance Details", "charge_lines", "customs")


def _rows_packing(opportunity):
	return _rows_from_child_charges(opportunity, "Packing Specification", "charge_lines", "packing")


def _rows_relocation(opportunity):
	return _rows_from_child_charges(opportunity, "Relocation Details", "charge_lines", "relocation")


def _rows_tpl(opportunity):
	"""3PL: bill inbound/outbound items at the contract's sell rate (cost-plus fallback)."""
	rows = []
	for parent_doctype, child_field in (
		("TPL Inbound Order", "inbound_items"),
		("TPL Outbound Order", "outbound_items"),
	):
		for pname in frappe.get_all(parent_doctype, filters={"opportunity": opportunity}, pluck="name"):
			parent = frappe.get_doc(parent_doctype, pname)
			for c in parent.get(child_field) or []:
				amount = flt(c.get("amount")) or (flt(c.get("rate")) * (cint(c.get("quantity")) or 1))
				if amount <= 0:
					continue
				item = c.get("charge_item") or _service_default_item("tpl")
				if not item:
					continue
				rows.append(_line(item, c.get("quantity") or 1, amount, c.get("rate") or amount, _default_tax_template("tpl")))
	return rows


SERVICE_BUILDERS = (_rows_air, _rows_sea, _rows_customs, _rows_packing, _rows_relocation, _rows_tpl)


def _service_default_item(service_key):
	s = _settings()
	if not s:
		return None
	return (s.get(f"{service_key}_charge_item") or "").strip() or None


def collect_logistics_rows(opportunity):
	rows = []
	for builder in SERVICE_BUILDERS:
		try:
			rows.extend(builder(opportunity))
		except Exception:
			# A broken/absent service doctype must never block the Opportunity save.
			frappe.log_error(frappe.get_traceback(), f"a3_logistics: {builder.__name__} failed")
	return rows


# --------------------------------------------------------------------------------------
# Main stacked validate hook
# --------------------------------------------------------------------------------------
def append_logistics_line_items(doc, method=None):
	# Pure Transport/Warehousing bookings with no logistics data: never touch the table.
	logistics_items = get_logistics_charge_items()
	has_existing = any(r.item in logistics_items for r in (doc.opportunity_line_item or []))

	new_rows = collect_logistics_rows(doc.name) if doc.name else []
	if not new_rows and not has_existing:
		return

	# Idempotent rebuild of ONLY logistics rows; keep every trip/warehouse row untouched.
	kept = [r.as_dict() for r in (doc.opportunity_line_item or []) if r.item not in logistics_items]
	doc.set("opportunity_line_item", [])
	for r in kept:
		doc.append("opportunity_line_item", r)
	for row in new_rows:
		if not row.get("tax_template"):
			row["tax_template"] = DEFAULT_TAX_TEMPLATE
		doc.append("opportunity_line_item", row)

	_recompute_totals(doc)


def _recompute_totals(doc):
	"""Re-run trip's total calc so logistics rows get VAT + payment_amount includes them.

	Reuses a3_trip_management's calculate_total_charges (does not reimplement). Falls back to a
	minimal sum if that import is unavailable, so a logistics save never hard-fails on coupling.
	"""
	try:
		from a3_trip_management.events.opportunity import calculate_total_charges

		calculate_total_charges(doc)
	except Exception:
		total = 0.0
		for item in doc.opportunity_line_item:
			total += flt(item.amount)
		# Best-effort only; trip normally owns payment_amount.
		if hasattr(doc, "payment_amount"):
			doc.payment_amount = total
