from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.osv import expression


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


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _route_positive_search_operator(self, operator):
        return operator in ("=", "ilike", "=ilike", "like", "=like")

    @api.model
    def _route_exact_search_operator(self, operator):
        return operator in ("=", "=ilike", "=like")

    @api.model
    def _route_packaging_product_ids(self, term, operator="ilike", limit=100):
        Packaging = self.env["product.packaging"]
        products = self.env["product.product"]
        if "barcode" in Packaging._fields:
            packagings = Packaging.search([("barcode", operator, term)], limit=limit)
            if "product_id" in Packaging._fields:
                products |= packagings.mapped("product_id")
            if "product_tmpl_id" in Packaging._fields:
                products |= packagings.mapped("product_tmpl_id.product_variant_ids")
        return products

    @api.model
    def _route_extra_barcode_products(self, term, operator="ilike", limit=100):
        term = (term or "").strip()
        if not term:
            return self.env["product.product"]

        products = self.env["product.product"]
        company = self.env.company

        products |= self.search([("barcode", operator, term)], limit=limit)
        if "default_code" in self._fields:
            products |= self.search([("default_code", operator, term)], limit=limit)

        barcode_lines = self.env["route.product.barcode"].search(
            [
                ("barcode", operator, term),
                ("company_id", "in", [False, company.id]),
            ],
            limit=limit,
        )
        products |= barcode_lines.mapped("product_id")

        if "product.packaging" in self.env:
            products |= self._route_packaging_product_ids(term, operator=operator, limit=limit)

        return products

    @api.model
    def _route_merge_ids(self, first_ids, extra_ids, limit=100):
        ordered = []
        seen = set()
        for pid in list(first_ids) + list(extra_ids):
            if not pid or pid in seen:
                continue
            seen.add(pid)
            ordered.append(pid)
            if limit and len(ordered) >= limit:
                break
        return ordered

    @api.model
    def _route_extra_search_ids(self, name, args=None, operator="ilike", limit=100, **kwargs):
        args = list(args or [])
        products = self.env["product.product"]

        if self._route_exact_search_operator(operator):
            products |= self._route_extra_barcode_products(name, operator="=", limit=limit)
        products |= self._route_extra_barcode_products(name, operator="ilike", limit=limit)

        if not products:
            return []

        return self._search(
            expression.AND([args, [("id", "in", products.ids)]]),
            limit=limit,
            **kwargs,
        )

    @api.model
    def _name_search(self, name="", args=None, operator="ilike", limit=100, **kwargs):
        args = list(args or [])
        base_ids = super()._name_search(name=name, args=args, operator=operator, limit=limit, **kwargs)
        if not name or not self._route_positive_search_operator(operator):
            return base_ids
        extra_ids = self._route_extra_search_ids(name, args=args, operator=operator, limit=limit, **kwargs)
        return self._route_merge_ids(base_ids, extra_ids, limit=limit)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def _route_positive_search_operator(self, operator):
        return operator in ("=", "ilike", "=ilike", "like", "=like")

    @api.model
    def _route_extra_template_ids(self, name, args=None, operator="ilike", limit=100, **kwargs):
        args = list(args or [])
        product_ids = self.env["product.product"]._route_extra_search_ids(
            name,
            args=[],
            operator=operator,
            limit=limit,
            **kwargs,
        )
        if not product_ids:
            return []
        templates = self.env["product.product"].browse(product_ids).mapped("product_tmpl_id")
        return self._search(
            expression.AND([args, [("id", "in", templates.ids)]]),
            limit=limit,
            **kwargs,
        )

    @api.model
    def _name_search(self, name="", args=None, operator="ilike", limit=100, **kwargs):
        args = list(args or [])
        base_ids = super()._name_search(name=name, args=args, operator=operator, limit=limit, **kwargs)
        if not name or not self._route_positive_search_operator(operator):
            return base_ids
        extra_ids = self._route_extra_template_ids(name, args=args, operator=operator, limit=limit, **kwargs)
        ordered = []
        seen = set()
        for tid in list(base_ids) + list(extra_ids):
            if not tid or tid in seen:
                continue
            seen.add(tid)
            ordered.append(tid)
            if limit and len(ordered) >= limit:
                break
        return ordered
