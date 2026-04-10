from odoo import api, fields, models


class RouteOutlet(models.Model):
    _inherit = "route.outlet"

    stock_location_id = fields.Many2one(
        "stock.location",
        string="Outlet Stock Location",
        domain=[("usage", "=", "internal")],
        ondelete="restrict",
        help="Internal stock location used for this outlet consignment/location mapping.",
    )

    def get_stock_location(self):
        self.ensure_one()
        return self.stock_location_id

    def has_stock_location(self):
        self.ensure_one()
        return bool(self.stock_location_id)

    def _sync_stock_balances_from_quants(self):
        Balance = self.env["outlet.stock.balance"].sudo()
        Quant = self.env["stock.quant"].sudo()
        Product = self.env["product.product"].sudo()

        for record in self.sudo():
            if record.outlet_operation_mode != "consignment" or not record.stock_location_id:
                continue

            balances = Balance.search([("outlet_id", "=", record.id)])
            existing_by_product = {balance.product_id.id: balance for balance in balances if balance.product_id}

            qty_by_product = {}
            quants = Quant.search([
                ("location_id", "child_of", record.stock_location_id.id),
                ("quantity", "!=", 0),
                ("product_id", "!=", False),
            ])
            for quant in quants:
                product_id = quant.product_id.id
                qty_by_product[product_id] = qty_by_product.get(product_id, 0.0) + (quant.quantity or 0.0)

            positive_qty_by_product = {
                product_id: qty
                for product_id, qty in qty_by_product.items()
                if qty > 0
            }

            for product in Product.browse(list(positive_qty_by_product.keys())):
                qty = positive_qty_by_product.get(product.id, 0.0)
                vals = {
                    "qty": qty,
                    "unit_price": product.lst_price or 0.0,
                    "company_id": record.company_id.id,
                }
                balance = existing_by_product.get(product.id)
                if balance:
                    balance.write(vals)
                else:
                    Balance.create({
                        "outlet_id": record.id,
                        "product_id": product.id,
                        **vals,
                    })

            for product_id, balance in existing_by_product.items():
                if product_id not in positive_qty_by_product:
                    balance.write({
                        "qty": 0.0,
                        "company_id": record.company_id.id,
                    })

        return True
