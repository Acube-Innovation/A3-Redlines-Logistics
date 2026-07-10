# Copyright (c) 2026, Acube and contributors
# For license information, please see license.txt
"""
Idempotent post-install seeding for a3_logistics. Runs only on `bench install-app a3_logistics`.

Creates ONLY a3_logistics-managed data — never edits trip/warehouse-owned records:
  * Role "Logistics Coordinator"
  * Item Group "Logistics Services" (the marker group used for idempotent line-item rebuild)
  * Default service charge Items (one per vertical) inside that group
  * Six Booking Type records (booking_type is trip-owned but data-driven; we add records only)
  * A3 Logistics Settings defaults

Every step checks for existence first, so re-running migrate/install never duplicates.
"""

import frappe

ITEM_GROUP = "Logistics Services"

# service_key, Item code/name, Booking Type label, location_required, inventory_required
SERVICES = [
	("air", "Air Freight", "Air Shipping", 1, 0),
	("sea", "Sea Freight", "Sea Shipping", 1, 0),
	("customs", "Customs Clearance", "Customs Clearance", 0, 0),
	("packing", "Industrial Packing", "Industrial Packing", 0, 1),
	("relocation", "Relocation", "Packing & Relocation", 1, 1),
	("tpl", "Third Party Logistics", "3PL Logistics & Distribution", 1, 1),
]


def after_install():
	"""Idempotent seeding. Defensive: a failure in any step is logged but never aborts the
	install — the app and its doctypes remain installed and seeding can be re-run from console
	via `a3_logistics.setup.install.after_install()`."""
	for step in (
		lambda: _ensure_role("Logistics Coordinator"),
		lambda: _ensure_item_group(ITEM_GROUP),
		_seed_service_items,
		_seed_booking_types,
		_seed_settings,
	):
		try:
			step()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(frappe.get_traceback(), "a3_logistics after_install step failed")
	frappe.db.commit()


def _seed_service_items():
	for _key, item_name, *_ in SERVICES:
		try:
			_ensure_service_item(item_name)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"a3_logistics: item seed failed {item_name}")


def _seed_booking_types():
	for _key, item_name, booking_label, loc, inv in SERVICES:
		try:
			_ensure_booking_type(booking_label, item_name, loc, inv)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"a3_logistics: booking type seed failed {booking_label}")


def _ensure_role(role_name):
	if not frappe.db.exists("Role", role_name):
		frappe.get_doc({"doctype": "Role", "role_name": role_name, "desk_access": 1}).insert(
			ignore_permissions=True
		)


def _ensure_item_group(group):
	if frappe.db.exists("Item Group", group):
		return
	parent = "All Item Groups" if frappe.db.exists("Item Group", "All Item Groups") else None
	doc = frappe.get_doc(
		{
			"doctype": "Item Group",
			"item_group_name": group,
			"is_group": 0,
			"parent_item_group": parent,
		}
	)
	doc.insert(ignore_permissions=True)


def _ensure_service_item(item_name):
	if frappe.db.exists("Item", item_name):
		return
	uom = "Nos" if frappe.db.exists("UOM", "Nos") else frappe.db.get_value("UOM", {}, "name")
	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": item_name,
			"item_name": item_name,
			"item_group": ITEM_GROUP,
			"stock_uom": uom,
			"is_stock_item": 0,
			"is_sales_item": 1,
			"is_purchase_item": 0,
		}
	).insert(ignore_permissions=True)


def _ensure_booking_type(label, item_name, location_required, inventory_required):
	if frappe.db.exists("Booking Type", label):
		return
	doc = frappe.get_doc(
		{
			"doctype": "Booking Type",
			"booking_type": label,
			"item": item_name if frappe.db.exists("Item", item_name) else None,
			"location_required": location_required,
			"inventory_required": inventory_required,
			"description": f"{label} (a3_logistics)",
		}
	)
	doc.insert(ignore_permissions=True)


def _seed_settings():
	s = frappe.get_single("A3 Logistics Settings")
	if not (s.get("logistics_item_group")):
		s.logistics_item_group = ITEM_GROUP
	# The two already-live services default ON; the new verticals stay OFF (Under Construction)
	# until an admin ticks them. Only set when unset so admin choices are never overwritten.
	for field in ("enable_transport", "enable_warehousing"):
		if s.get(field) is None:
			s.set(field, 1)
	for key, item_name, *_ in SERVICES:
		field = f"{key}_charge_item"
		if hasattr(s, field) and not s.get(field) and frappe.db.exists("Item", item_name):
			s.set(field, item_name)
	s.flags.ignore_permissions = True
	s.save(ignore_permissions=True)
