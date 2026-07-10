# Copyright (c) 2026, Acube and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class AirShipmentDetails(Document):
	def validate(self):
		self.set_chargeable_weight()
		self.calculate_freight()

	def set_chargeable_weight(self):
		if not flt(self.chargeable_weight):
			self.chargeable_weight = max(flt(self.gross_weight), flt(self.volumetric_weight))

	def calculate_freight(self):
		"""Derive freight_amount from the linked Air Freight Tariff. Self-contained: never
		touches Opportunity or Tariff Details. The opportunity-level handler reads freight_amount."""
		if not self.air_freight_tariff:
			# Keep any manually-entered amount; otherwise leave at 0 until a tariff is chosen.
			return
		tariff = frappe.get_cached_doc("Air Freight Tariff", self.air_freight_tariff)
		basis = tariff.rate_basis or "Per KG"
		if basis == "Per KG":
			self.rate = flt(tariff.rate_per_kg)
			amount = self.rate * flt(self.chargeable_weight)
		elif basis == "Per CBM":
			self.rate = flt(tariff.rate_per_cbm)
			cbm = self._total_volume_cbm()
			amount = self.rate * cbm
		else:  # Per Shipment
			self.rate = flt(tariff.min_charge)
			amount = self.rate
		self.freight_amount = max(amount, flt(tariff.min_charge))
		if not self.charge_item and tariff.charge_item:
			self.charge_item = tariff.charge_item

	def _total_volume_cbm(self):
		total = 0.0
		for p in self.package_lines or []:
			# cm^3 -> CBM
			total += (flt(p.length) * flt(p.width) * flt(p.height)) / 1_000_000.0
		return total
