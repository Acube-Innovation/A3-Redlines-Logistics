# Copyright (c) 2026, Acube and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import cint, flt


class RelocationDetails(Document):
	def validate(self):
		self.calculate_charges()

	def calculate_charges(self):
		total = 0.0
		for c in self.charge_lines or []:
			c.amount = flt(c.rate) * (cint(c.quantity) or 1)
			total += flt(c.amount)
		self.total_amount = total
