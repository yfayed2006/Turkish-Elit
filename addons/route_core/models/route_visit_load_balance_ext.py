from collections import defaultdict

from odoo import fields, models, _
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _inherit = "route.visit"

    def _get_default_source_location(self):
        self.ensure_one()
        return self.source_location_id or self.vehicle_id.stock_location_id

    def _sync_source_location_from_vehicle(self):
        for rec in self:
            source_location = rec._get_default_source_location()
            if source_location and rec.source_location_id != source_location:
                rec.source_location_id = source_location

    def _get_vehicle_available_qty_for_product(self, product):
        self.ensure_one()

        source_location = self._get_default_source_location()
        if not source_location or not product:
            return 0.0

        quants = self.env["stock.quant"].search([
            ("location_id", "child_of", source_location.id),
            ("product_id", "=", product.id),
        ])
        return sum(quants.mapped("quantity"))

    def _update_vehicle_available_on_lines(self, lines=None):
        for rec in self:
            rec._sync_source_location_from_vehicle()
            target_lines = lines if lines is not None else rec.line_ids
            for line in target_lines.filtered(lambda l: l.product_id):
                line.vehicle_available_qty = rec._get_vehicle_available_qty_for_product(
                    line.product_id
                )

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

        balance_model = self.env["outlet.stock.balance"]
        result = []

        for product_id, qty in qty_by_product.items():
            product = self.env["product.product"].browse(product_id)

            existing_balance = balance_model.search([
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
        route_visit_line = self.env["route.visit.line"]

        for rec in self:
            if hasattr(rec, "_is_direct_sales_stop") and rec._is_direct_sales_stop():
                raise UserError(_("Load Previous Balance is not available for Direct Sales stops."))

            if rec.state != "in_progress":
                raise UserError(
                    _("Previous balance can only be loaded while the visit is in progress.")
                )

            if rec.visit_process_state not in ("pending", "checked_in"):
                raise UserError(
                    _("Previous balance can only be loaded right after starting the visit.")
                )

            if not rec.outlet_id:
                raise UserError(_("Please set an outlet before loading previous balance."))

            if not rec.vehicle_id:
                raise UserError(_("Please set a vehicle before loading previous balance."))

            if not rec.vehicle_id.stock_location_id:
                raise UserError(
                    _("The selected vehicle does not have a Vehicle Stock Location.")
                )

            if rec.line_ids:
                raise UserError(_(
                    "This visit already has lines. Remove existing lines first if you want to reload previous balance."
                ))

            rec._sync_source_location_from_vehicle()

            balance_rows = rec._get_outlet_previous_balance_from_stock_location()

            if not balance_rows:
                balance_rows = rec._get_outlet_previous_balance_fallback_records()

            if not balance_rows:
                if rec.outlet_id.stock_location_id:
                    raise UserError(_(
                        "No previous stock balance was found for this outlet. "
                        "The linked outlet stock location exists, but no positive quantities were found in it."
                    ))
                raise UserError(_("No previous stock balance was found for this outlet."))

            line_vals_list = []
            for row in balance_rows:
                product = self.env["product.product"].browse(row["product_id"])
                vehicle_available_qty = rec._get_vehicle_available_qty_for_product(product)

                line_vals_list.append({
                    "visit_id": rec.id,
                    "company_id": rec.company_id.id,
                    "product_id": row["product_id"],
                    "previous_qty": row["qty"],
                    "unit_price": row["unit_price"],
                    "vehicle_available_qty": vehicle_available_qty,
                })

            created_lines = route_visit_line.create(line_vals_list)
            rec._update_vehicle_available_on_lines(created_lines)

            vals = {
                "visit_process_state": "checked_in",
            }
            if "check_in_datetime" in rec._fields:
                vals["check_in_datetime"] = rec.check_in_datetime or fields.Datetime.now()
            rec.write(vals)

        return True

    def action_generate_refill_proposal(self):
        for rec in self:
            if hasattr(rec, "_is_direct_sales_stop") and rec._is_direct_sales_stop():
                raise UserError(_("Refill Proposal is not available for Direct Sales stops."))

            if rec.visit_process_state != "reconciled":
                raise UserError(
                    _("Refill proposal can only be generated when the visit is in Reconciled state.")
                )

            if not rec.line_ids:
                raise UserError(_("There are no visit lines to generate a refill proposal."))

            rec._sync_source_location_from_vehicle()

            if not rec.source_location_id:
                raise UserError(_("Please select Source Location before generating refill proposal."))

            rec._update_vehicle_available_on_lines()

            has_supplied_qty = False
            for line in rec.line_ids:
                available_qty = line.vehicle_available_qty or 0.0
                sold_qty = line.sold_qty or 0.0
                proposed_qty = min(sold_qty, available_qty) if sold_qty > 0 else 0.0
                pending_qty = max(sold_qty - proposed_qty, 0.0)
                line.write({
                    "supplied_qty": proposed_qty,
                    "pending_refill_qty": pending_qty,
                })
                has_supplied_qty = has_supplied_qty or proposed_qty > 0

            rec.write({
                "has_refill": has_supplied_qty,
            })
