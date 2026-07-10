# Copyright (c) 2026, Acube and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import flt


class TPLVendorContract(Document):
	def validate(self):
		self.derive_sell_rates()

	def derive_sell_rates(self):
		"""Cost-plus fallback: when a rate line has no sell_rate, derive it from buy_rate
		using the contract markup. Self-contained; never touches Opportunity."""
		for line in self.rate_lines or []:
			if not flt(line.sell_rate) and flt(line.buy_rate):
				line.sell_rate = flt(line.buy_rate) * (1 + flt(self.markup_percent) / 100)
