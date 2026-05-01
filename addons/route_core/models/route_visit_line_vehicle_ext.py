from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare


class RouteVisitLine(models.Model):
    _inherit = "route.visit.line"

    vehicle_product_ids = fields.Many2many(
        "product.product",
        string="Vehicle Products",
        compute="_compute_vehicle_product_ids",
        store=False,
    )

    @api.model
    def _route_get_quant_available_field(self):
        Quant = self.env["stock.quant"].with_user(SUPERUSER_ID).sudo()
        return "available_quantity" if "available_quantity" in Quant._fields else "quantity"

    def _route_get_vehicle_source_location(self):
        self.ensure_one()
        visit = self.visit_id
        if not visit:
            return self.env["stock.location"]
        if hasattr(visit, "_get_default_source_location"):
            return visit._get_default_source_location()
        return visit.source_location_id or visit.vehicle_id.stock_location_id

    @api.depends("visit_id", "visit_id.source_location_id", "visit_id.vehicle_id")
    def _compute_vehicle_product_ids(self):
        Product = self.env["product.product"].with_user(SUPERUSER_ID).sudo()
        Quant = self.env["stock.quant"].with_user(SUPERUSER_ID).sudo()
        qty_field = self._route_get_quant_available_field()

        for line in self:
            products = Product.browse()
            source_location = line._route_get_vehicle_source_location()

            if source_location:
                quants = Quant.search([
                    ("location_id", "child_of", source_location.id),
                    (qty_field, ">", 0),
                ])
                products = quants.mapped("product_id")

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
        qty_field = self._route_get_quant_available_field()
        domain = [
            ("location_id", "child_of", source_location.id),
            ("product_id", "=", product.id),
            (qty_field, ">", 0),
        ]
        if lot:
            domain.append(("lot_id", "=", lot.id))

        return sum(max(getattr(quant, qty_field, 0.0) or 0.0, 0.0) for quant in Quant.search(domain))

    @api.onchange("visit_id", "product_id", "lot_id")
    def _onchange_vehicle_available_qty(self):
        for line in self:
            if line.product_id:
                line.vehicle_available_qty = line._get_vehicle_available_qty(
                    line.product_id,
                    lot=line.lot_id if line.lot_id else False,
                )
            else:
                line.vehicle_available_qty = 0.0

    @api.model_create_multi
    def create(self, vals_list):
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
            if float_compare(line.supplied_qty, available_qty, precision_digits=precision) > 0:
                raise ValidationError(_(
                    "Qty to Refill cannot be greater than the vehicle available quantity.\n\n"
                    "Product: %(product)s\nAvailable in vehicle: %(available).2f\nQty to refill: %(qty).2f"
                ) % {
                    "product": line.product_id.display_name,
                    "available": available_qty,
                    "qty": line.supplied_qty or 0.0,
                })
