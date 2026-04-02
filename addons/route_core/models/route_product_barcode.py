from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.osv import expression


class RouteProductBarcode(models.Model):
    _name = "route.product.barcode"
    _description = "Route Product Barcode"
    _order = "product_id, barcode_type, id"

    name = fields.Char(string="Name", compute="_compute_name", store=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company, required=True, index=True)
    product_id = fields.Many2one("product.product", string="Product", required=True, ondelete="cascade", index=True)
    barcode = fields.Char(string="Barcode", required=True, index=True)
    barcode_type = fields.Selection([("piece", "Piece"), ("box", "Box")], string="Barcode Type", required=True, default="piece")
    qty_in_base_uom = fields.Float(string="Qty in Base UoM", required=True, default=1.0, help="How many base units should be added when this barcode is scanned.")
    notes = fields.Char(string="Notes")

    @api.depends("product_id", "barcode", "barcode_type", "qty_in_base_uom")
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.product_id.display_name or ''} / {rec.barcode_type or ''} / {rec.barcode or ''} / {rec.qty_in_base_uom or 0.0}"

    @api.constrains("barcode", "qty_in_base_uom")
    def _check_values(self):
        for rec in self:
            if not rec.barcode or not rec.barcode.strip():
                raise ValidationError(_("Barcode is required."))
            if rec.qty_in_base_uom <= 0:
                raise ValidationError(_("Qty in Base UoM must be greater than zero."))

    _sql_constraints = [(
        "route_product_barcode_barcode_company_uniq",
        "unique(barcode, company_id)",
        "Barcode must be unique per company.",
    )]


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

        for domain in ([('barcode', '=', term)], [('default_code', '=', term)]):
            if _add_products(self.search(domain, limit=limit)):
                return product_ids

        route_barcode_domain = [('active', '=', True), ('barcode', barcode_operator, term)]
        if 'company_id' in self.env['route.product.barcode']._fields:
            route_barcode_domain = expression.AND([
                [('active', '=', True)],
                ['|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)],
                [('barcode', barcode_operator, term)],
            ])
        route_barcodes = self.env['route.product.barcode'].search(route_barcode_domain, limit=limit)
        if _add_products(route_barcodes.mapped('product_id')):
            return product_ids

        Packaging = self.env['product.packaging']
        if 'barcode' in Packaging._fields:
            packaging_domain = [('barcode', barcode_operator, term)]
            if 'company_id' in Packaging._fields:
                packaging_domain = expression.AND([
                    ['|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)],
                    packaging_domain,
                ])
            packagings = Packaging.search(packaging_domain, limit=limit)
            packaging_products = self.browse()
            if 'product_id' in Packaging._fields:
                packaging_products |= packagings.mapped('product_id')
            if 'product_tmpl_id' in Packaging._fields:
                packaging_products |= packagings.mapped('product_tmpl_id.product_variant_ids')
            if _add_products(packaging_products):
                return product_ids

        fallback_domain = ['|', ('barcode', barcode_operator, term), ('default_code', barcode_operator, term)]
        _add_products(self.search(fallback_domain, limit=limit))
        return product_ids

    @api.model
    def _route_name_search_label(self, product, search_term=None):
        search_term = (search_term or '').strip()
        code = False
        if search_term:
            if product.barcode and search_term.lower() in (product.barcode or '').lower():
                code = product.barcode
            elif product.default_code and search_term.lower() in (product.default_code or '').lower():
                code = product.default_code
            else:
                route_code = self.env['route.product.barcode'].search([
                    ('product_id', '=', product.id),
                    ('barcode', 'ilike', search_term),
                    ('active', '=', True),
                ], limit=1)
                if route_code:
                    code = route_code.barcode
                else:
                    Packaging = self.env['product.packaging']
                    packaging = False
                    if 'barcode' in Packaging._fields and 'product_id' in Packaging._fields:
                        packaging = Packaging.search([
                            ('product_id', '=', product.id),
                            ('barcode', 'ilike', search_term),
                        ], limit=1)
                    if not packaging and 'barcode' in Packaging._fields and 'product_tmpl_id' in Packaging._fields:
                        packaging = Packaging.search([
                            ('product_tmpl_id', '=', product.product_tmpl_id.id),
                            ('barcode', 'ilike', search_term),
                        ], limit=1)
                    if packaging:
                        code = packaging.barcode
        if not code:
            code = product.barcode or product.default_code
        return f"[{code}] {product.display_name}" if code else product.display_name

    @api.model
    def _name_search(self, name="", args=None, operator="ilike", limit=100, order=None):
        args = list(args or [])
        term = (name or '').strip()
        if term:
            barcode_ids = self._route_collect_barcode_product_ids(term, operator=operator, limit=limit)
            if barcode_ids:
                domain = expression.AND([args, [('id', 'in', barcode_ids)]])
                ids = list(self._search(domain, limit=limit, order=order))
                if ids:
                    return ids
        return super()._name_search(name, args, operator, limit, order)

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        args = list(args or [])
        term = (name or '').strip()
        if term:
            barcode_ids = self._route_collect_barcode_product_ids(term, operator=operator, limit=limit)
            if barcode_ids:
                domain = expression.AND([args, [('id', 'in', barcode_ids)]])
                records = self.search(domain, limit=limit)
                if records:
                    return [(product.id, self._route_name_search_label(product, term)) for product in records]
        return super().name_search(name, args, operator, limit)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def _name_search(self, name="", args=None, operator="ilike", limit=100, order=None):
        args = list(args or [])
        term = (name or '').strip()
        if term:
            product_ids = self.env['product.product']._route_collect_barcode_product_ids(term, operator=operator, limit=limit)
            if product_ids:
                template_ids = self.env['product.product'].browse(product_ids).mapped('product_tmpl_id').ids
                if template_ids:
                    domain = expression.AND([args, [('id', 'in', template_ids)]])
                    ids = list(self._search(domain, limit=limit, order=order))
                    if ids:
                        return ids
        return super()._name_search(name, args, operator, limit, order)

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        args = list(args or [])
        term = (name or '').strip()
        if term:
            product_ids = self.env['product.product']._route_collect_barcode_product_ids(term, operator=operator, limit=limit)
            if product_ids:
                products = self.env['product.product'].browse(product_ids)
                templates = products.mapped('product_tmpl_id')
                # preserve product order as much as possible, one row per template
                result = []
                seen = set()
                for product in products:
                    tmpl = product.product_tmpl_id
                    if tmpl.id in seen:
                        continue
                    seen.add(tmpl.id)
                    result.append((tmpl.id, self.env['product.product']._route_name_search_label(product, term)))
                    if limit and len(result) >= limit:
                        break
                if result:
                    return result
        return super().name_search(name, args, operator, limit)
