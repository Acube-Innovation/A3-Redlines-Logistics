# Copyright (c) 2026, Acube and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class SeaShipmentDetails(Document):
	def validate(self):
		self.calculate_freight()

	def calculate_freight(self):
		"""Derive freight_amount from the linked Sea Freight Tariff. Self-contained: never
		touches Opportunity or Tariff Details. The opportunity-level handler reads freight_amount."""
		if not self.sea_freight_tariff:
			# Keep any manually-entered amount; otherwise leave at 0 until a tariff is chosen.
			return
		tariff = frappe.get_cached_doc("Sea Freight Tariff", self.sea_freight_tariff)
		if self.shipment_mode == "LCL":
			self.rate = flt(tariff.rate_per_cbm)
			amount = self.rate * self._total_cbm()
		else:  # FCL
			self.rate = flt(tariff.rate_per_container)
			amount = self.rate * len(self.container_lines or [])
		self.freight_amount = max(amount, flt(tariff.min_charge))
		if not self.charge_item and tariff.charge_item:
			self.charge_item = tariff.charge_item

	def _total_cbm(self):
		total = 0.0
		for c in self.container_lines or []:
			total += flt(c.cbm)
		return total
