# Copyright (c) 2026, Acube and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import cint, flt


class TPLInboundOrder(Document):
	def validate(self):
		self.calculate_amounts()

	def calculate_amounts(self):
		"""Self-contained line + total amount calc. The opportunity-level handler reads
		each row's amount; never touches Opportunity here."""
		total = 0.0
		for line in self.inbound_items or []:
			line.amount = flt(line.rate) * (cint(line.quantity) or 1)
			total += flt(line.amount)
		self.total_amount = total
