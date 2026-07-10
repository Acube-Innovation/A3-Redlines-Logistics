# Copyright (c) 2026, Acube and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import cint, flt


class PackingSpecification(Document):
	def validate(self):
		self.calculate_charges()

	def calculate_charges(self):
		total = 0.0
		for row in self.charge_lines or []:
			row.amount = flt(row.rate) * (cint(row.quantity) or 1)
			total += flt(row.amount)
		self.total_amount = total
