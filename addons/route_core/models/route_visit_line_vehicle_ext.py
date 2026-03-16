from odoo import api, fields, models


class RouteVisitLine(models.Model):
    _inherit = "route.visit.line"

    vehicle_product_ids = fields.Many2many(
        "product.product",
        string="Vehicle Products",
        compute="_compute_vehicle_product_ids",
        store=False,
    )

    @api.depends("visit_id", "visit_id.source_location_id", "visit_id.vehicle_id")
    def _compute_vehicle_product_ids(self):
        Quant = self.env["stock.quant"]

        for line in self:
            products = self.env["product.product"]

            source_location = (
                line.visit_id.source_location_id
                or line.visit_id.vehicle_id.stock_location_id
            )

            if source_location:
                quants = Quant.search([
                    ("location_id", "child_of", source_location.id),
                    ("quantity", ">", 0),
                ])
                products = quants.mapped("product_id")

            line.vehicle_product_ids = products

    def _get_vehicle_available_qty(self, product=None):
        self.ensure_one()

        product = product or self.product_id
        visit = self.visit_id

        if not visit or not product:
            return 0.0

        source_location = visit.source_location_id or visit.vehicle_id.stock_location_id
        if not source_location:
            return 0.0

        quants = self.env["stock.quant"].search([
            ("location_id", "child_of", source_location.id),
            ("product_id", "=", product.id),
        ])
        return sum(quants.mapped("quantity"))

    @api.onchange("visit_id", "product_id")
    def _onchange_vehicle_available_qty(self):
        for line in self:
            if line.product_id:
                line.vehicle_available_qty = line._get_vehicle_available_qty()
            else:
                line.vehicle_available_qty = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines.filtered(lambda l: l.product_id and l.visit_id):
            line.vehicle_available_qty = line._get_vehicle_available_qty()
        return lines

    def write(self, vals):
        result = super().write(vals)
        tracked_fields = {"visit_id", "product_id"}
        if tracked_fields.intersection(vals.keys()):
            for line in self.filtered(lambda l: l.product_id and l.visit_id):
                line.vehicle_available_qty = line._get_vehicle_available_qty()
        return result
