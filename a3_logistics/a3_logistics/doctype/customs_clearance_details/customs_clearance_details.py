# Copyright (c) 2026, Acube and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import cint, flt


class CustomsClearanceDetails(Document):
	def validate(self):
		self.calculate_charges()

	def calculate_charges(self):
		"""Compute each charge line's amount and the document total. Self-contained: never
		touches Opportunity. The opportunity-level handler reads charge_lines (charge_item,
		quantity, rate, amount, is_pass_through)."""
		total = 0.0
		for line in self.charge_lines or []:
			line.amount = flt(line.rate) * (cint(line.quantity) or 1)
			total += flt(line.amount)
		self.total_amount = total
