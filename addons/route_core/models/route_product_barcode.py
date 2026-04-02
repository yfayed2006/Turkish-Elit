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
    def _route_get_products_from_packaging(self, packaging_records):
        products = self.env["product.product"]
        for packaging in packaging_records:
            product = False
            if "product_id" in packaging._fields and packaging.product_id:
                product = packaging.product_id
            elif "product_tmpl_id" in packaging._fields and packaging.product_tmpl_id:
                product = packaging.product_tmpl_id.product_variant_ids[:1]
            if product:
                products |= product
        return products

    @api.model
    def _route_search_extra_barcode_products(self, term, operator="ilike", limit=100):
        term = (term or "").strip()
        if not term:
            return self.env["product.product"]

        products = self.env["product.product"]

        try:
            barcode_lines = self.env["route.product.barcode"].search([
                ("barcode", operator, term)
            ], limit=limit)
            products |= barcode_lines.mapped("product_id")
        except Exception:
            pass

        if "product.packaging" in self.env:
            Packaging = self.env["product.packaging"]
            seen_fields = set()
            for field_name, field in Packaging._fields.items():
                try:
                    if getattr(field, "type", None) != "char":
                        continue
                    if "barcode" not in field_name:
                        continue
                    if field_name in seen_fields:
                        continue
                    seen_fields.add(field_name)
                    packaging_records = Packaging.search([
                        (field_name, operator, term)
                    ], limit=limit)
                    products |= self._route_get_products_from_packaging(packaging_records)
                except Exception:
                    continue

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
    def _name_search(self, name="", args=None, operator="ilike", limit=100, name_get_uid=None):
        args = list(args or [])
        if not name:
            return super()._name_search(name=name, args=args, operator=operator, limit=limit, name_get_uid=name_get_uid)

        positive_ops = ("=", "ilike", "=ilike", "like", "=like")
        exact_ops = ("=", "=ilike", "=like")

        if operator in positive_ops:
            exact_hits = self.env["product.product"]
            if operator in exact_ops:
                exact_hits |= self._route_search_extra_barcode_products(name, operator="=", limit=limit)
                if exact_hits:
                    exact_ids = super()._name_search(name=name, args=args + [("id", "in", exact_hits.ids)], operator=operator, limit=limit, name_get_uid=name_get_uid)
                    if exact_ids:
                        return exact_ids
                    return self._search(expression.AND([args, [("id", "in", exact_hits.ids)]]), limit=limit, access_rights_uid=name_get_uid)

            base_ids = super()._name_search(name=name, args=args, operator=operator, limit=limit, name_get_uid=name_get_uid)
            extra_products = self._route_search_extra_barcode_products(name, operator="ilike", limit=limit)
            if extra_products:
                extra_ids = self._search(expression.AND([args, [("id", "in", extra_products.ids)]]), limit=limit, access_rights_uid=name_get_uid)
                return self._route_merge_ids(base_ids, extra_ids, limit=limit)
            return base_ids

        return super()._name_search(name=name, args=args, operator=operator, limit=limit, name_get_uid=name_get_uid)
