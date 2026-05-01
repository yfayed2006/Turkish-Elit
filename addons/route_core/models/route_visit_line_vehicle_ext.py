from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


class RouteVisitLine(models.Model):
    _inherit = "route.visit.line"

    vehicle_product_ids = fields.Many2many(
        "product.product",
        string="Vehicle Products",
        compute="_compute_vehicle_product_ids",
        store=False,
    )
    route_manual_refill_line = fields.Boolean(
        string="Manual Refill Line",
        default=False,
        copy=False,
        help="Technical flag used for products manually added by the salesperson during refill confirmation.",
    )
    can_delete_refill_line = fields.Boolean(
        string="Can Delete Refill Line",
        compute="_compute_can_delete_refill_line",
        store=False,
    )

    @api.model
    def _route_get_quant_available_field(self):
        Quant = self.env["stock.quant"].with_user(SUPERUSER_ID).sudo()
        return "available_quantity" if "available_quantity" in Quant._fields else "quantity"

    def _route_get_quant_available_qty(self, quant):
        """Return available qty without using non-stored fields in SQL domains.

        In Odoo 19, stock.quant.available_quantity is computed and not stored,
        so it cannot be used in a search domain. We search by stored fields only
        and read the available value in Python.
        """
        qty_field = self._route_get_quant_available_field()
        return max(getattr(quant, qty_field, 0.0) or 0.0, 0.0)

    def _route_get_vehicle_source_location(self):
        self.ensure_one()
        visit = self.visit_id
        if not visit:
            return self.env["stock.location"]
        if hasattr(visit, "_get_default_source_location"):
            return visit._get_default_source_location()
        return visit.source_location_id or visit.vehicle_id.stock_location_id

    def _route_is_refill_edit_stage(self):
        self.ensure_one()
        visit = self.visit_id
        return bool(
            visit
            and not (getattr(visit, "_is_direct_sales_stop", False) and visit._is_direct_sales_stop())
            and visit.visit_process_state in ("reconciled", "collection_done", "ready_to_close")
            and visit.state == "in_progress"
        )

    def _route_is_manual_refill_candidate(self):
        self.ensure_one()
        precision = self.env["decimal.precision"].precision_get("Product Unit of Measure") or 2
        return (
            self._route_is_refill_edit_stage()
            and float_is_zero(self.previous_qty or 0.0, precision_digits=precision)
            and float_is_zero(self.counted_qty or 0.0, precision_digits=precision)
            and float_is_zero(self.return_qty or 0.0, precision_digits=precision)
            and float_is_zero(self.sold_qty or 0.0, precision_digits=precision)
            and float_is_zero(self.pending_refill_qty or 0.0, precision_digits=precision)
        )

    @api.depends("visit_id", "previous_qty", "counted_qty", "return_qty", "sold_qty", "pending_refill_qty", "route_manual_refill_line")
    def _compute_can_delete_refill_line(self):
        for line in self:
            line.can_delete_refill_line = bool(line.route_manual_refill_line or line._route_is_manual_refill_candidate())

    @api.depends("visit_id", "visit_id.source_location_id", "visit_id.vehicle_id")
    def _compute_vehicle_product_ids(self):
        Product = self.env["product.product"].with_user(SUPERUSER_ID).sudo()
        Quant = self.env["stock.quant"].with_user(SUPERUSER_ID).sudo()

        for line in self:
            products = Product.browse()
            source_location = line._route_get_vehicle_source_location()

            if source_location:
                quants = Quant.search([
                    ("location_id", "child_of", source_location.id),
                ])
                products = quants.filtered(
                    lambda quant: line._route_get_quant_available_qty(quant) > 0
                ).mapped("product_id")

            line.vehicle_product_ids = products

    def _get_vehicle_available_qty(self, product=None, lot=False):
        self.ensure_one()

        product = (product or self.product_id).with_user(SUPERUSER_ID).sudo()
        if not self.visit_id or not product:
            return 0.0

        source_location = self._route_get_vehicle_source_location()
        if not source_location:
            return 0.0

        Quant = self.env["stock.quant"].with_user(SUPERUSER_ID).sudo()
        domain = [
            ("location_id", "child_of", source_location.id),
            ("product_id", "=", product.id),
        ]
        if lot:
            domain.append(("lot_id", "=", lot.id))

        return sum(
            qty for qty in (
                self._route_get_quant_available_qty(quant)
                for quant in Quant.search(domain)
            )
            if qty > 0
        )

    def _get_other_refill_qty_for_same_stock(self):
        self.ensure_one()
        if not self.visit_id or not self.product_id:
            return 0.0

        other_lines = self.visit_id.with_user(SUPERUSER_ID).sudo().line_ids.filtered(
            lambda l: l.id != self.id
            and l.product_id.id == self.product_id.id
            and (l.supplied_qty or 0.0) > 0
        )
        if self.lot_id:
            other_lines = other_lines.filtered(lambda l: l.lot_id.id == self.lot_id.id)

        return sum(other_lines.mapped("supplied_qty"))

    def _get_vehicle_refill_remaining_qty(self):
        self.ensure_one()
        available_qty = self._get_vehicle_available_qty(
            self.product_id,
            lot=self.lot_id if self.lot_id else False,
        )
        other_refill_qty = self._get_other_refill_qty_for_same_stock()
        return max(available_qty - other_refill_qty, 0.0)

    @api.onchange("visit_id", "product_id", "lot_id")
    def _onchange_vehicle_available_qty(self):
        warning = False
        for line in self:
            if line.product_id:
                available_qty = line._get_vehicle_available_qty(
                    line.product_id,
                    lot=line.lot_id if line.lot_id else False,
                )
                line.vehicle_available_qty = available_qty

                if line._route_is_manual_refill_candidate() and available_qty <= 0:
                    product_name = line.product_id.display_name
                    line.product_id = False
                    line.lot_id = False
                    line.supplied_qty = 0.0
                    warning = {
                        "title": _("Product is not available in the vehicle"),
                        "message": _(
                            "%(product)s is not available in the selected vehicle stock location. "
                            "Only products currently available in the vehicle can be added to this refill."
                        ) % {"product": product_name},
                    }
            else:
                line.vehicle_available_qty = 0.0
        if warning:
            return {"warning": warning}
        return None

    @api.onchange("supplied_qty", "approved_refill_qty", "approved_refill_qty_display", "product_id", "lot_id", "visit_id")
    def _onchange_refill_qty_not_above_vehicle_stock(self):
        warning = False
        precision = self.env["decimal.precision"].precision_get("Product Unit of Measure") or 2
        for line in self:
            if not line.product_id or not line._route_is_refill_edit_stage():
                continue

            remaining_qty = line._get_vehicle_refill_remaining_qty()
            current_qty = line.supplied_qty or 0.0
            if float_compare(current_qty, remaining_qty, precision_digits=precision) > 0:
                line.supplied_qty = remaining_qty
                warning = {
                    "title": _("Refill quantity adjusted"),
                    "message": _(
                        "Qty to refill cannot be greater than the vehicle available quantity.\n\n"
                        "Product: %(product)s\nAvailable to add now: %(available).2f\nEntered qty: %(qty).2f\n\n"
                        "The approved refill quantity has been adjusted to %(available).2f."
                    ) % {
                        "product": line.product_id.display_name,
                        "available": remaining_qty,
                        "qty": current_qty,
                    },
                }
        if warning:
            return {"warning": warning}
        return None

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            visit_id = vals.get("visit_id")
            if visit_id and not vals.get("route_manual_refill_line"):
                visit = self.env["route.visit"].browse(visit_id)
                if visit and visit.visit_process_state in ("reconciled", "collection_done", "ready_to_close"):
                    previous_qty = vals.get("previous_qty") or 0.0
                    counted_qty = vals.get("counted_qty") or 0.0
                    return_qty = vals.get("return_qty") or 0.0
                    pending_refill_qty = vals.get("pending_refill_qty") or 0.0
                    if not previous_qty and not counted_qty and not return_qty and not pending_refill_qty:
                        vals["route_manual_refill_line"] = True

        lines = super().create(vals_list)
        for line in lines.filtered(lambda l: l.product_id and l.visit_id):
            line.vehicle_available_qty = line._get_vehicle_available_qty(
                line.product_id,
                lot=line.lot_id if line.lot_id else False,
            )
        return lines

    def write(self, vals):
        result = super().write(vals)
        tracked_fields = {"visit_id", "product_id", "lot_id"}
        if tracked_fields.intersection(vals.keys()):
            for line in self.filtered(lambda l: l.product_id and l.visit_id):
                line.vehicle_available_qty = line._get_vehicle_available_qty(
                    line.product_id,
                    lot=line.lot_id if line.lot_id else False,
                )
        return result

    def action_remove_refill_line(self):
        for line in self:
            if not line.can_delete_refill_line:
                raise ValidationError(_("Only manually added refill lines can be removed from this step."))
        self.unlink()
        return True

    def unlink(self):
        protected_lines = self.filtered(
            lambda line: line.visit_id
            and line.visit_id.visit_process_state in ("reconciled", "collection_done", "ready_to_close")
            and not line.can_delete_refill_line
        )
        if protected_lines:
            raise ValidationError(_("Only manually added refill lines can be removed from this step."))
        return super().unlink()

    @api.constrains("product_id", "supplied_qty", "visit_id", "lot_id")
    def _check_refill_qty_available_in_vehicle(self):
        precision = self.env["decimal.precision"].precision_get("Product Unit of Measure") or 2
        for line in self:
            if not line.visit_id or not line.product_id or (line.supplied_qty or 0.0) <= 0:
                continue
            visit = line.visit_id
            if getattr(visit, "_is_direct_sales_stop", False) and visit._is_direct_sales_stop():
                continue
            if visit.visit_process_state not in ("reconciled", "collection_done", "ready_to_close"):
                continue

            available_qty = line._get_vehicle_available_qty(
                line.product_id,
                lot=line.lot_id if line.lot_id else False,
            )
            other_refill_qty = line._get_other_refill_qty_for_same_stock()
            remaining_qty = max(available_qty - other_refill_qty, 0.0)
            if float_compare(line.supplied_qty, remaining_qty, precision_digits=precision) > 0:
                raise ValidationError(_(
                    "Qty to Refill cannot be greater than the vehicle available quantity.\n\n"
                    "Product: %(product)s\nAvailable in vehicle: %(available).2f\nAlready approved on other lines: %(other).2f\nAvailable to add now: %(remaining).2f\nQty to refill: %(qty).2f"
                ) % {
                    "product": line.product_id.display_name,
                    "available": available_qty,
                    "other": other_refill_qty,
                    "remaining": remaining_qty,
                    "qty": line.supplied_qty or 0.0,
                })
