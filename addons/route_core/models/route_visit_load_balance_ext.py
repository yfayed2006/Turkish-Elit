from collections import defaultdict

from odoo import fields, models, _
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _inherit = "route.visit"

    def _get_outlet_previous_balance_from_stock_location(self):
        self.ensure_one()

        outlet = self.outlet_id
        location = outlet.stock_location_id

        if not location:
            return []

        quants = self.env["stock.quant"].search([
            ("location_id", "child_of", location.id),
            ("quantity", ">", 0),
        ])

        qty_by_product = defaultdict(float)
        for quant in quants:
            if quant.product_id and quant.quantity > 0:
                qty_by_product[quant.product_id.id] += quant.quantity

        if not qty_by_product:
            return []

        Balance = self.env["outlet.stock.balance"]
        result = []

        for product_id, qty in qty_by_product.items():
            product = self.env["product.product"].browse(product_id)

            existing_balance = Balance.search([
                ("outlet_id", "=", outlet.id),
                ("product_id", "=", product_id),
            ], limit=1)

            unit_price = (
                existing_balance.unit_price
                if existing_balance and existing_balance.unit_price
                else (product.lst_price or 0.0)
            )

            result.append({
                "product_id": product_id,
                "qty": qty,
                "unit_price": unit_price,
            })

        result.sort(key=lambda x: x["product_id"])
        return result

    def _get_outlet_previous_balance_fallback_records(self):
        self.ensure_one()

        balances = self.env["outlet.stock.balance"].search([
            ("outlet_id", "=", self.outlet_id.id),
            ("qty", ">", 0),
        ])

        result = []
        for balance in balances:
            result.append({
                "product_id": balance.product_id.id,
                "qty": balance.qty,
                "unit_price": balance.unit_price,
            })
        return result

    def action_load_previous_balance(self):
        RouteVisitLine = self.env["route.visit.line"]

        for rec in self:
            if rec.visit_process_state not in ("pending",):
                raise UserError(_("Previous balance can only be loaded while the visit is Pending."))

            if not rec.outlet_id:
                raise UserError(_("Please set an outlet before loading previous balance."))

            if rec.line_ids:
                raise UserError(_(
                    "This visit already has lines. Remove existing lines first if you want to reload previous balance."
                ))

            balance_rows = rec._get_outlet_previous_balance_from_stock_location()

            if not balance_rows:
                balance_rows = rec._get_outlet_previous_balance_fallback_records()

            if not balance_rows:
                if rec.outlet_id.stock_location_id:
                    raise UserError(_(
                        "No previous stock balance was found for this outlet. "
                        "The linked outlet stock location exists, but no positive quantities were found in it."
                    ))
                raise UserError(_(
                    "No previous stock balance was found for this outlet."
                ))

            if (
                hasattr(rec.outlet_id, "default_commission_rate")
                and rec.outlet_id.default_commission_rate
            ):
                rec.commission_rate = rec.outlet_id.default_commission_rate

            line_vals_list = []
            for row in balance_rows:
                line_vals_list.append({
                    "visit_id": rec.id,
                    "company_id": rec.company_id.id,
                    "product_id": row["product_id"],
                    "previous_qty": row["qty"],
                    "unit_price": row["unit_price"],
                })

            RouteVisitLine.create(line_vals_list)

            rec.write({
                "visit_process_state": "checked_in",
                "check_in_datetime": rec.check_in_datetime or fields.Datetime.now(),
            })
