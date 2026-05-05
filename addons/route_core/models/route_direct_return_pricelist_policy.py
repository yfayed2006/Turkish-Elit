from odoo import api, fields, models


class RouteDirectReturn(models.Model):
    _inherit = "route.direct.return"

    amount_untaxed = fields.Monetary(
        string="Return Untaxed",
        compute="_compute_route_tax_policy_amounts",
        currency_field="currency_id",
        store=False,
    )
    amount_tax = fields.Monetary(
        string="Return Tax",
        compute="_compute_route_tax_policy_amounts",
        currency_field="currency_id",
        store=False,
    )

    def _route_get_effective_pricelist(self):
        """Open Direct Return pricing policy.

        Field returns can include old outlet stock that is not linked to the
        current sale order. Reference Sale Order / Delivery is therefore used
        for tracking only. Prices, discounts, and taxes come from the outlet's
        direct-sale/customer pricelist.
        """
        self.ensure_one()
        outlet = self.outlet_id
        if outlet and getattr(outlet, "direct_sale_pricelist_id", False):
            return outlet.direct_sale_pricelist_id
        partner = outlet.partner_id if outlet else self.partner_id
        if partner and getattr(partner, "property_product_pricelist", False):
            return partner.property_product_pricelist
        return self.env["product.pricelist"]

    @api.depends(
        "line_ids.estimated_untaxed_amount",
        "line_ids.estimated_tax_amount",
        "line_ids.estimated_total_amount",
        "line_ids.estimated_amount",
    )
    def _compute_route_tax_policy_amounts(self):
        for rec in self:
            rec.amount_untaxed = sum(rec.line_ids.mapped("estimated_untaxed_amount")) if rec.line_ids else 0.0
            rec.amount_tax = sum(rec.line_ids.mapped("estimated_tax_amount")) if rec.line_ids else 0.0

    @api.depends("line_ids.estimated_total_amount", "line_ids.estimated_amount")
    def _compute_amount_total(self):
        """Keep existing settlement logic on amount_total, but make it tax-aware.

        Older Route Core logic summed estimated_amount. The new tax display adds
        estimated_total_amount. We keep amount_total as the confirmed return
        value that reduces the settlement, so it should use total-including-tax
        when tax data exists, and safely fall back to estimated_amount.
        """
        for rec in self:
            total = 0.0
            for line in rec.line_ids:
                total += line.estimated_total_amount or line.estimated_amount or 0.0
            rec.amount_total = total


class RouteDirectReturnLine(models.Model):
    _inherit = "route.direct.return.line"

    estimated_untaxed_amount = fields.Monetary(
        string="Untaxed Amount",
        compute="_compute_estimated_amount",
        currency_field="currency_id",
        store=False,
    )
    estimated_tax_amount = fields.Monetary(
        string="Tax Amount",
        compute="_compute_estimated_amount",
        currency_field="currency_id",
        store=False,
    )
    estimated_total_amount = fields.Monetary(
        string="Total Incl. Tax",
        compute="_compute_estimated_amount",
        currency_field="currency_id",
        store=False,
    )

    @api.depends("return_id", "return_id.outlet_id")
    def _compute_route_available_product_ids(self):
        Product = self.env["product.product"]
        saleable_products = Product.search([("sale_ok", "=", True)])
        for line in self:
            line.route_available_product_ids = saleable_products

    def _route_product_allowed_by_reference(self, product):
        # Open Direct Return policy: reference documents are tracking only and
        # must not restrict products returned from the outlet.
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

    def _route_get_base_unit_price_for_discount(self):
        self.ensure_one()
        product = self.product_id
        if not product:
            return 0.0
        base_price = product.lst_price or 0.0
        uom = self.uom_id or product.uom_id
        if uom and product.uom_id and uom != product.uom_id:
            try:
                base_price = product.uom_id._compute_price(base_price, uom)
            except Exception:
                pass
        return base_price

    def _route_get_pricelist_discount_percent(self, pricelist=False):
        """Approximate the visible discount from the outlet pricelist.

        Odoo pricelists usually return the net unit price. For the salesperson
        card we want the same practical display as sale lines: public/base unit
        price plus discount when the pricelist reduces the price.
        """
        self.ensure_one()
        base_price = self._route_get_base_unit_price_for_discount()
        pricelist_price = self._route_get_outlet_pricelist_return_unit_price()
        if base_price and pricelist_price and pricelist_price < base_price:
            return max(0.0, min(100.0, (1.0 - (pricelist_price / base_price)) * 100.0))
        return 0.0

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
                line.estimated_untaxed_amount = 0.0
                line.estimated_tax_amount = 0.0
                line.estimated_total_amount = 0.0
                line.reference_discount = 0.0
                line.route_reference_tax_ids = False
                continue

            pricelist_price = line._route_get_outlet_pricelist_return_unit_price()
            base_unit_price = line._route_get_base_unit_price_for_discount()
            discount = line._route_get_pricelist_discount_percent(line._route_get_return_pricelist())

            if discount:
                unit_price = base_unit_price or pricelist_price
            else:
                unit_price = pricelist_price

            taxes = line._route_get_pricelist_taxes()
            line.route_reference_tax_ids = taxes
            line.estimated_unit_price = unit_price or 0.0
            line.reference_discount = discount or 0.0

            discount_factor = 1.0 - ((line.reference_discount or 0.0) / 100.0)
            price_after_discount = (line.estimated_unit_price or 0.0) * discount_factor
            quantity = line.quantity or 0.0
            untaxed = quantity * price_after_discount
            tax_amount = 0.0
            total = untaxed

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
                    untaxed = tax_result.get("total_excluded", untaxed)
                    total = tax_result.get("total_included", untaxed)
                    tax_amount = total - untaxed
                except Exception:
                    tax_amount = 0.0
                    total = untaxed

            # estimated_amount is kept as the settlement-facing return value for
            # compatibility with existing Route Core logic and reports.
            line.estimated_untaxed_amount = untaxed
            line.estimated_tax_amount = tax_amount
            line.estimated_total_amount = total
            line.estimated_amount = total
