from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.osv import expression



class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _route_collect_packaging_product_ids(self, barcode_value, operator="="):
        Packaging = self.env["product.packaging"]
        if not barcode_value or "barcode" not in Packaging._fields:
            return []

        packaging_domain = [("barcode", operator, barcode_value)]
        packagings = Packaging.search(packaging_domain)
        product_ids = []
        for packaging in packagings:
            if "product_id" in packaging._fields and packaging.product_id:
                product_ids.append(packaging.product_id.id)
            elif "product_tmpl_id" in packaging._fields and packaging.product_tmpl_id:
                product_ids.extend(packaging.product_tmpl_id.product_variant_ids.ids)
        return list(dict.fromkeys(product_ids))

    @api.model
    def _route_collect_custom_barcode_product_ids(self, barcode_value, operator="="):
        if not barcode_value or "route.product.barcode" not in self.env:
            return []

        mappings = self.env["route.product.barcode"].search([("barcode", operator, barcode_value)])
        return list(dict.fromkeys(mappings.mapped("product_id").ids))

    @api.model
    def _route_filter_searchable_product_ids(self, candidate_ids, args=None, limit=100, order=None):
        candidate_ids = list(dict.fromkeys(candidate_ids or []))
        if not candidate_ids:
            return []
        domain = expression.AND([list(args or []), [("id", "in", candidate_ids)]])
        return self.search(domain, limit=limit, order=order).ids

    @api.model
    def _name_search(self, name="", args=None, operator="ilike", limit=100, order=None):
        args = list(args or [])
        if not name:
            return super()._name_search(name=name, args=args, operator=operator, limit=limit, order=order)

        result_ids = []
        exact_match_operators = {"=", "=like", "=ilike"}
        fuzzy_match_operators = {"like", "ilike", "=", "=like", "=ilike"}

        if operator in fuzzy_match_operators:
            exact_candidate_ids = []
            if "barcode" in self._fields:
                exact_candidate_ids.extend(
                    self.search(expression.AND([args, [("barcode", "=", name)]]), limit=limit, order=order).ids
                )
            if "default_code" in self._fields:
                exact_candidate_ids.extend(
                    self.search(expression.AND([args, [("default_code", "=", name)]]), limit=limit, order=order).ids
                )
            exact_candidate_ids.extend(self._route_filter_searchable_product_ids(
                self._route_collect_custom_barcode_product_ids(name, operator="="),
                args=args,
                limit=limit,
                order=order,
            ))
            exact_candidate_ids.extend(self._route_filter_searchable_product_ids(
                self._route_collect_packaging_product_ids(name, operator="="),
                args=args,
                limit=limit,
                order=order,
            ))
            result_ids.extend(list(dict.fromkeys(exact_candidate_ids)))

            if operator not in exact_match_operators:
                fuzzy_candidate_ids = []
                fuzzy_candidate_ids.extend(self._route_filter_searchable_product_ids(
                    self._route_collect_custom_barcode_product_ids(name, operator=operator),
                    args=args,
                    limit=limit,
                    order=order,
                ))
                fuzzy_candidate_ids.extend(self._route_filter_searchable_product_ids(
                    self._route_collect_packaging_product_ids(name, operator=operator),
                    args=args,
                    limit=limit,
                    order=order,
                ))
                for product_id in fuzzy_candidate_ids:
                    if product_id not in result_ids:
                        result_ids.append(product_id)

        super_limit = None
        if limit:
            super_limit = max(limit - len(result_ids), 0)
        if super_limit is None or super_limit > 0:
            super_ids = super()._name_search(name=name, args=args, operator=operator, limit=super_limit, order=order)
            for product_id in super_ids:
                if product_id not in result_ids:
                    result_ids.append(product_id)

        return result_ids[:limit] if limit else result_ids


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
