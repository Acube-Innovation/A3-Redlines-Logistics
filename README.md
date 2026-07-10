## A3 Logistics

Backend business logic for new logistics service verticals on the `redlines` site —
**3PL Logistics & Distribution, Air Shipping, Sea Shipping, Customs Clearance,
Industrial Packing, and Packing & Relocation**.

This app is **additive** and coexists with `a3_trip_management`, `a3_warehouse_management`,
and `a3_webconsole` without modifying any of them:

- **Opportunity stays the single booking master.** Each service stores its data in this app's
  own doctypes, every one carrying an `opportunity` Link back to the master. No custom fields
  are added to `Opportunity`.
- **Tariff stays the single pricing engine.** New rate data lives in standalone `a3_logistics`
  rate doctypes. `Tariff Details` is left byte-for-byte unchanged.
- **One save, never an out-of-band `opp.save()`.** A *stacked* `Opportunity.validate` handler
  (`a3_logistics.events.opportunity.append_logistics_line_items`) re-derives and appends
  logistics rows to `opportunity_line_item` after `a3_trip_management`'s rebuild, then re-runs
  `calculate_total_charges` so the rows receive identical VAT/total treatment. No handler calls
  `Opportunity.save()`.
- **Frontend stays in `a3_webconsole`.** This app ships only doctypes, hooks, and whitelisted APIs.

See `A3_LOGISTICS_ARCHITECTURE.md` at the bench root for the full coexistence design and the
open approval gates.

#### License

mit
