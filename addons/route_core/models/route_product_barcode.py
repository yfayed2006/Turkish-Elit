from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class RouteProductBarcode(models.Model):
    _name = "route.product.barcode"
    _description = "Route Product Barcode"
    _order = "product_id, barcode_type, id"

    name = fields.Char(
        string="Name",
        compute="_compute_name",
        store=True,
    )
    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        ondelete="cascade",
        index=True,
    )

    barcode = fields.Char(
        string="Barcode",
        required=True,
        index=True,
    )

    barcode_type = fields.Selection(
        [
            ("piece", "Piece"),
            ("box", "Box"),
        ],
        string="Barcode Type",
        required=True,
        default="piece",
    )

    qty_in_base_uom = fields.Float(
        string="Qty in Base UoM",
        required=True,
        default=1.0,
        help="How many base units should be added when this barcode is scanned.",
    )

    notes = fields.Char(string="Notes")

    @api.depends("product_id", "barcode", "barcode_type", "qty_in_base_uom")
    def _compute_name(self):
        for rec in self:
            product_name = rec.product_id.display_name or ""
            barcode = rec.barcode or ""
            barcode_type = rec.barcode_type or ""
            qty = rec.qty_in_base_uom or 0.0
            rec.name = f"{product_name} / {barcode_type} / {barcode} / {qty}"

    @api.constrains("barcode", "qty_in_base_uom")
    def _check_values(self):
        for rec in self:
            if not rec.barcode or not rec.barcode.strip():
                raise ValidationError(_("Barcode is required."))
            if rec.qty_in_base_uom <= 0:
                raise ValidationError(_("Qty in Base UoM must be greater than zero."))

    _sql_constraints = [
        (
            "route_product_barcode_barcode_company_uniq",
            "unique(barcode, company_id)",
            "Barcode must be unique per company.",
        ),
    ]
