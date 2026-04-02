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


from odoo.osv import expression


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _route_collect_barcode_product_ids(self, name, operator="ilike", limit=100):
        term = (name or "").strip()
        if not term:
            return []

        product_ids = []
        seen = set()

        def _add_products(products):
            for product in products:
                if product.id not in seen:
                    seen.add(product.id)
                    product_ids.append(product.id)
                    if limit and len(product_ids) >= limit:
                        return True
            return False

        barcode_operator = operator if operator in ("=", "ilike", "like", "=ilike", "=like") else "ilike"

        # 1) exact / direct fields on product.product
        direct_domains = [
            [("barcode", "=", term)],
            [("default_code", "=", term)],
        ]
        for domain in direct_domains:
            if _add_products(self.search(domain, limit=limit)):
                return product_ids

        # 2) route.product.barcode custom barcodes
        RouteBarcode = self.env["route.product.barcode"]
        route_barcode_domain = [("barcode", barcode_operator, term), ("active", "=", True)]
        if "company_id" in RouteBarcode._fields:
            route_barcode_domain = expression.AND([
                [("active", "=", True)],
                ["|", ("company_id", "=", False), ("company_id", "=", self.env.company.id)],
                [("barcode", barcode_operator, term)],
            ])
        route_barcodes = RouteBarcode.search(route_barcode_domain, limit=limit)
        if _add_products(route_barcodes.mapped("product_id")):
            return product_ids

        # 3) packaging barcodes
        if "product.packaging" in self.env:
            Packaging = self.env["product.packaging"]
            packaging_domain = [("barcode", barcode_operator, term)] if "barcode" in Packaging._fields else []
            if packaging_domain:
                if "company_id" in Packaging._fields:
                    packaging_domain = expression.AND([
                        ["|", ("company_id", "=", False), ("company_id", "=", self.env.company.id)],
                        packaging_domain,
                    ])
                packagings = Packaging.search(packaging_domain, limit=limit)
                packaging_products = self.browse()
                for field_name in ("product_id", "product_tmpl_id"):
                    if field_name not in Packaging._fields:
                        continue
                    values = packagings.mapped(field_name)
                    if not values:
                        continue
                    if getattr(values, "_name", "") == "product.template":
                        packaging_products |= values.mapped("product_variant_ids")
                    else:
                        packaging_products |= values
                if _add_products(packaging_products):
                    return product_ids

        # 4) fallback direct ilike on product barcode / internal reference
        fallback_domain = ["|", ("barcode", barcode_operator, term), ("default_code", barcode_operator, term)]
        _add_products(self.search(fallback_domain, limit=limit))
        return product_ids

    @api.model
    def _name_search(self, name="", args=None, operator="ilike", limit=100, order=None):
        args = list(args or [])
        term = (name or "").strip()
        if term:
            barcode_ids = self._route_collect_barcode_product_ids(term, operator=operator, limit=limit)
            if barcode_ids:
                domain = expression.AND([args, [("id", "in", barcode_ids)]])
                return list(self._search(domain, limit=limit, order=order))
        return super()._name_search(name=name, args=args, operator=operator, limit=limit, order=order)

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        term = (name or "").strip()
        if term:
            barcode_ids = self._route_collect_barcode_product_ids(term, operator=operator, limit=limit)
            if barcode_ids:
                records = self.browse(barcode_ids)
                if limit:
                    records = records[:limit]
                return records.get_formatted_display_name()
        return super().name_search(name=name, args=args, operator=operator, limit=limit)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def _name_search(self, name="", args=None, operator="ilike", limit=100, order=None):
        args = list(args or [])
        term = (name or "").strip()
        if term:
            product_ids = self.env["product.product"]._route_collect_barcode_product_ids(term, operator=operator, limit=limit)
            if product_ids:
                template_ids = self.env["product.product"].browse(product_ids).mapped("product_tmpl_id").ids
                if template_ids:
                    domain = expression.AND([args, [("id", "in", template_ids)]])
                    return list(self._search(domain, limit=limit, order=order))
        return super()._name_search(name=name, args=args, operator=operator, limit=limit, order=order)

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        term = (name or "").strip()
        if term:
            product_ids = self.env["product.product"]._route_collect_barcode_product_ids(term, operator=operator, limit=limit)
            if product_ids:
                templates = self.env["product.product"].browse(product_ids).mapped("product_tmpl_id")
                if limit:
                    templates = templates[:limit]
                return templates.get_formatted_display_name()
        return super().name_search(name=name, args=args, operator=operator, limit=limit)
