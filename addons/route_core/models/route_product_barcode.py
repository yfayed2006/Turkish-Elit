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
    def _route_apply_source_available_domain(self, domain=None):
        source_domain = self._route_source_available_domain()
        domain = list(domain or [])
        return expression.AND([domain, source_domain]) if source_domain else domain

    @api.model
    def _route_source_available_domain(self):
        if not self.env.context.get("route_only_source_available_products"):
            return []
        location_id = self.env.context.get("route_source_location_id")
        if not location_id:
            return [("id", "=", 0)]

        quant_domain = [
            ("location_id", "child_of", location_id),
            ("quantity", ">", 0),
            ("product_id.sale_ok", "=", True),
            ("product_id.active", "=", True),
        ]
        if "detailed_type" in self._fields:
            quant_domain.append(("product_id.detailed_type", "in", ["product", "consu"]))

        quants = self.env["stock.quant"].search(quant_domain)
        available_by_product = {}
        for quant in quants:
            product = quant.product_id
            if not product:
                continue
            reserved = quant.reserved_quantity if "reserved_quantity" in quant._fields else 0.0
            available_qty = max((quant.quantity or 0.0) - (reserved or 0.0), 0.0)
            if available_qty <= 0:
                continue
            available_by_product[product.id] = available_by_product.get(product.id, 0.0) + available_qty
        product_ids = [product_id for product_id, qty in available_by_product.items() if qty > 0]
        return [("id", "in", product_ids or [0])]

    @api.model
    def _route_barcode_domain(self, term, operator="ilike"):
        op = operator if operator in ("=", "ilike", "like", "=ilike", "=like") else "ilike"
        return ["|", ("barcode", op, term), ("default_code", op, term)]

    @api.model
    def _route_collect_barcode_product_ids(self, term, operator="ilike", limit=100, extra_domain=None):
        term = (term or "").strip()
        extra_domain = list(extra_domain or [])
        if not term:
            return []

        result_ids = []
        seen = set()

        def _add_products(products):
            for product in products:
                if product.id not in seen:
                    seen.add(product.id)
                    result_ids.append(product.id)
                    if limit and len(result_ids) >= limit:
                        return True
            return False

        def _search_products(domain):
            full_domain = expression.AND([extra_domain, domain]) if extra_domain else domain
            return self.search(full_domain, limit=limit)

        # 1) direct exact match on product barcode / internal reference
        if _add_products(_search_products(["|", ("barcode", "=", term), ("default_code", "=", term)])):
            return result_ids

        # 2) custom route product barcode exact match
        RouteBarcode = self.env["route.product.barcode"]
        route_barcode_domain = [("barcode", "=", term)]
        if "active" in RouteBarcode._fields:
            route_barcode_domain.append(("active", "=", True))
        if "company_id" in RouteBarcode._fields:
            route_barcode_domain = expression.AND([
                ["|", ("company_id", "=", False), ("company_id", "=", self.env.company.id)],
                route_barcode_domain,
            ])
        route_barcodes = RouteBarcode.search(route_barcode_domain, limit=limit)
        if route_barcodes:
            route_products = self.browse(route_barcodes.mapped("product_id").ids)
            if extra_domain:
                route_products = route_products.search(expression.AND([extra_domain, [("id", "in", route_products.ids)]]), limit=limit)
            if _add_products(route_products):
                return result_ids

        # 3) packaging barcode exact match
        Packaging = self.env["product.packaging"] if "product.packaging" in self.env else False
        if Packaging and "barcode" in Packaging._fields:
            packaging_domain = [("barcode", "=", term)]
            if "company_id" in Packaging._fields:
                packaging_domain = expression.AND([
                    ["|", ("company_id", "=", False), ("company_id", "=", self.env.company.id)],
                    packaging_domain,
                ])
            packagings = Packaging.search(packaging_domain, limit=limit)
            packaging_products = self.browse()
            if packagings:
                if "product_id" in Packaging._fields:
                    packaging_products |= packagings.mapped("product_id")
                if "product_tmpl_id" in Packaging._fields:
                    packaging_products |= packagings.mapped("product_tmpl_id.product_variant_ids")
                packaging_products = self.browse(packaging_products.ids)
                if extra_domain:
                    packaging_products = packaging_products.search(expression.AND([extra_domain, [("id", "in", packaging_products.ids)]]), limit=limit)
                if _add_products(packaging_products):
                    return result_ids

        # 4) ilike fallback on barcode / internal reference / custom / packaging
        if _add_products(_search_products(self._route_barcode_domain(term, operator=operator))):
            return result_ids

        route_barcode_domain = [("barcode", operator if operator in ("=", "ilike", "like", "=ilike", "=like") else "ilike", term)]
        if "active" in RouteBarcode._fields:
            route_barcode_domain.append(("active", "=", True))
        if "company_id" in RouteBarcode._fields:
            route_barcode_domain = expression.AND([
                ["|", ("company_id", "=", False), ("company_id", "=", self.env.company.id)],
                route_barcode_domain,
            ])
        route_barcodes = RouteBarcode.search(route_barcode_domain, limit=limit)
        if route_barcodes:
            route_products = self.browse(route_barcodes.mapped("product_id").ids)
            if extra_domain:
                route_products = route_products.search(expression.AND([extra_domain, [("id", "in", route_products.ids)]]), limit=limit)
            if _add_products(route_products):
                return result_ids

        if Packaging and "barcode" in Packaging._fields:
            packaging_domain = [("barcode", operator if operator in ("=", "ilike", "like", "=ilike", "=like") else "ilike", term)]
            if "company_id" in Packaging._fields:
                packaging_domain = expression.AND([
                    ["|", ("company_id", "=", False), ("company_id", "=", self.env.company.id)],
                    packaging_domain,
                ])
            packagings = Packaging.search(packaging_domain, limit=limit)
            packaging_products = self.browse()
            if packagings:
                if "product_id" in Packaging._fields:
                    packaging_products |= packagings.mapped("product_id")
                if "product_tmpl_id" in Packaging._fields:
                    packaging_products |= packagings.mapped("product_tmpl_id.product_variant_ids")
                packaging_products = self.browse(packaging_products.ids)
                if extra_domain:
                    packaging_products = packaging_products.search(expression.AND([extra_domain, [("id", "in", packaging_products.ids)]]), limit=limit)
                _add_products(packaging_products)

        return result_ids

    @api.model
    def _route_find_product_by_barcode(self, barcode, extra_domain=None):
        product_ids = self._route_collect_barcode_product_ids(barcode, operator="=", limit=1, extra_domain=extra_domain)
        return self.browse(product_ids[:1]) if product_ids else self.browse()

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, access_rights_uid=None):
        domain = self._route_apply_source_available_domain(domain)
        return super()._search(domain, offset=offset, limit=limit, order=order, access_rights_uid=access_rights_uid)

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        domain = self._route_apply_source_available_domain(domain)
        term = (name or "").strip()
        if term:
            product_ids = self._route_collect_barcode_product_ids(term, operator=operator, limit=limit, extra_domain=domain)
            if product_ids:
                records = self.browse(product_ids)
                return [(rec.id, rec.display_name) for rec in records[:limit]]
        return super().name_search(name, domain, operator, limit)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def _route_source_available_template_domain(self):
        product_domain = self.env["product.product"]._route_source_available_domain()
        if not product_domain:
            return []
        available_template_ids = self.env["product.product"].with_context(route_only_source_available_products=False).search(product_domain).mapped("product_tmpl_id").ids
        return [("id", "in", available_template_ids or [0])]

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, access_rights_uid=None):
        source_domain = self._route_source_available_template_domain()
        domain = list(domain or [])
        domain = expression.AND([domain, source_domain]) if source_domain else domain
        return super()._search(domain, offset=offset, limit=limit, order=order, access_rights_uid=access_rights_uid)

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        domain = list(domain or [])
        product_domain = self.env["product.product"]._route_source_available_domain()
        source_template_domain = self._route_source_available_template_domain()
        term = (name or "").strip()
        if term:
            product_ids = self.env["product.product"]._route_collect_barcode_product_ids(
                term,
                operator=operator,
                limit=limit,
                extra_domain=product_domain,
            )
            if product_ids:
                template_ids = self.env["product.product"].browse(product_ids).mapped("product_tmpl_id").ids
                if template_ids:
                    templates = self.search(expression.AND([domain, [("id", "in", template_ids)]]), limit=limit)
                    if templates:
                        return [(rec.id, rec.display_name) for rec in templates[:limit]]
        if source_template_domain:
            domain = expression.AND([domain, source_template_domain])
        return super().name_search(name, domain, operator, limit)

