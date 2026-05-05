from odoo import api, fields, models


class RouteDirectReturn(models.Model):
    _inherit = "route.direct.return"

    def _route_get_effective_pricelist(self):
        """Direct Return pricing policy for open field returns.

        Reference Sale Order / Reference Delivery is optional tracking only.
        Returned products may be old stock found at the outlet, so their price,
        discount, and taxes must be calculated from the outlet/customer direct-sale
        pricelist, not copied from a selected reference sale order.
        """
        self.ensure_one()
        outlet = self.outlet_id
        if outlet and getattr(outlet, "direct_sale_pricelist_id", False):
            return outlet.direct_sale_pricelist_id
        partner = outlet.partner_id if outlet else self.partner_id
        if partner and getattr(partner, "property_product_pricelist", False):
            return partner.property_product_pricelist
        return self.env["product.pricelist"]


class RouteDirectReturnLine(models.Model):
    _inherit = "route.direct.return.line"

    @api.depends("return_id", "return_id.outlet_id")
    def _compute_route_available_product_ids(self):
        Product = self.env["product.product"]
        saleable_products = Product.search([("sale_ok", "=", True)])
        for line in self:
            line.route_available_product_ids = saleable_products

    def _route_product_allowed_by_reference(self, product):
        # Open Direct Return policy: reference documents are tracking only and
        # must not restrict the products that can be returned from the outlet.
        return True

    def _route_get_return_pricelist(self):
        self.ensure_one()
        if self.return_id:
            return self.return_id._route_get_effective_pricelist()
        return self.env["product.pricelist"]

    def _route_get_outlet_pricelist_return_unit_price(self):
        self.ensure_one()
        product = self.product_id
        direct_return = self.return_id
        if not product:
            return 0.0

        pricelist = self._route_get_return_pricelist()
        quantity = self.quantity or 1.0
        uom = self.uom_id or product.uom_id
        partner = direct_return.partner_id if direct_return else False
        return_date = direct_return.return_date if direct_return else fields.Date.context_today(self)

        if pricelist and hasattr(pricelist, "_get_product_price"):
            try:
                return pricelist._get_product_price(
                    product,
                    quantity,
                    partner=partner,
                    date=return_date,
                    uom_id=uom,
                ) or 0.0
            except TypeError:
                try:
                    return pricelist._get_product_price(product, quantity, partner) or 0.0
                except Exception:
                    pass
            except Exception:
                pass
        return product.lst_price or 0.0

    def _route_get_pricelist_taxes(self):
        self.ensure_one()
        product = self.product_id
        company = self.return_id.company_id if self.return_id else self.env.company
        partner = self.return_id.partner_id if self.return_id else False
        if not product:
            return self.env["account.tax"]

        taxes = product.taxes_id.filtered(lambda tax: not tax.company_id or tax.company_id == company)
        fiscal_position = getattr(partner, "property_account_position_id", False) if partner else False
        if fiscal_position and hasattr(fiscal_position, "map_tax"):
            taxes = fiscal_position.map_tax(taxes)
        return taxes

    @api.depends(
        "product_id",
        "quantity",
        "uom_id",
        "return_id",
        "return_id.outlet_id",
        "return_id.outlet_id.direct_sale_pricelist_id",
        "return_id.outlet_id.partner_id.property_product_pricelist",
        "return_id.partner_id",
    )
    def _compute_estimated_amount(self):
        for line in self:
            product = line.product_id
            if not product:
                line.estimated_unit_price = 0.0
                line.estimated_amount = 0.0
                line.estimated_tax_amount = 0.0
                line.estimated_total_amount = 0.0
                line.reference_discount = 0.0
                line.route_reference_tax_ids = False
                continue

            pricelist = line._route_get_return_pricelist()
            pricelist_discount = False
            if hasattr(line, "_route_get_pricelist_discount_percent"):
                pricelist_discount = line._route_get_pricelist_discount_percent(pricelist)

            if pricelist_discount is not False:
                unit_price = 0.0
                if hasattr(line, "_route_get_base_unit_price_for_discount"):
                    unit_price = line._route_get_base_unit_price_for_discount() or 0.0
                if not unit_price:
                    unit_price = line._route_get_outlet_pricelist_return_unit_price()
                line.reference_discount = pricelist_discount or 0.0
            else:
                unit_price = line._route_get_outlet_pricelist_return_unit_price()
                line.reference_discount = 0.0

            taxes = line._route_get_pricelist_taxes()
            line.route_reference_tax_ids = taxes
            line.estimated_unit_price = unit_price

            discount_factor = 1.0 - ((line.reference_discount or 0.0) / 100.0)
            price_after_discount = (unit_price or 0.0) * discount_factor
            quantity = line.quantity or 0.0
            subtotal = quantity * price_after_discount
            tax_amount = 0.0
            total = subtotal

            if taxes:
                currency = line.currency_id or (line.return_id.currency_id if line.return_id else False) or line.env.company.currency_id
                partner = line.return_id.partner_id if line.return_id else False
                try:
                    tax_result = taxes.compute_all(
                        price_after_discount,
                        currency=currency,
                        quantity=quantity,
                        product=product,
                        partner=partner,
                    )
                    subtotal = tax_result.get("total_excluded", subtotal)
                    total = tax_result.get("total_included", subtotal)
                    tax_amount = total - subtotal
                except Exception:
                    tax_amount = 0.0
                    total = subtotal

            line.estimated_amount = subtotal
            line.estimated_tax_amount = tax_amount
            line.estimated_total_amount = total
