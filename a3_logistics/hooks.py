app_name = "a3_logistics"
app_title = "A3 Logistics"
app_publisher = "Acube"
app_description = "Backend business logic for new logistics service verticals (3PL, Air, Sea, Customs, Industrial Packing, Relocation)"
app_email = "acube@acube.co"
app_license = "mit"

# Apps
# ------------------

# a3_logistics reads pricing/billing helpers from a3_trip_management and stacks a handler
# behind its Opportunity.validate. Declare the dependency explicitly (the existing apps leave
# this commented; we fix that fragility here). a3_logistics MUST be ordered AFTER
# a3_warehouse_management in sites/apps.txt so its validate handler runs last and its
# dashboard override receives the already-merged data.
# required_apps = ["a3_trip_management"]

# Document Events
# ---------------
# Stacked, additive hooks only. a3_trip_management's Opportunity.validate runs first (loads
# first); this handler runs after it and APPENDS logistics rows to opportunity_line_item.
# No handler here ever calls Opportunity.save() (avoids TimestampMismatchError).
doc_events = {
	"Opportunity": {
		"validate": "a3_logistics.events.opportunity.append_logistics_line_items",
	},
	# NOTE: By default a3_logistics does NOT hook Stock Entry / Delivery Note. 3PL holds GRN /
	# Delivery Note as read-only references so it never trips a3_warehouse_management's existing
	# on_submit handlers (order_status='Stock Updated' / Customer Request 'Delivered').
	# Enable the line below only after Approval Gate 8 is signed off:
	# "Delivery Note": {"on_submit": "a3_logistics.events.delivery_note.on_submit"},
}

# Scheduled Tasks
# ---------------
# Only 3PL has period accrual. Unique path + idempotency-keyed ledger (mirrors Warehouse
# Storage Charge). Does NOT pre-empt a3_trip_management.generate_monthly_warehouse_invoices.
scheduler_events = {
	"daily_long": [
		"a3_logistics.events.billing.generate_logistics_invoices",
	],
}

# Dashboard overrides
# -------------------
# Additive MERGE only (append a "Logistics" group + merge non_standard_fieldnames). Never
# replaces incoming data, so a3_trip_management / a3_warehouse_management sections survive.
override_doctype_dashboards = {
	"Opportunity": "a3_logistics.overrides.opportunity_dashboard.get_data",
}

# Installation
# ------------
after_install = "a3_logistics.setup.install.after_install"

# Fixtures
# --------
# Only a3_logistics-owned records. NEVER exports Custom Field / Custom DocPerm for
# trip/warehouse-owned doctypes (zero collision). Booking Type records and logistics Items
# are created idempotently in after_install (they depend on other data), not exported here.
fixtures = [
	{"dt": "Role", "filters": [["role_name", "in", ["Logistics Coordinator"]]]},
]
