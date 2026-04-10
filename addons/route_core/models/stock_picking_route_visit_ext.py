from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    route_visit_id = fields.Many2one(
        "route.visit",
        string="Route Visit",
        index=True,
        copy=False,
        ondelete="set null",
    )

    def _get_related_consignment_outlets_for_balance_sync(self):
        self.ensure_one()
        outlet_model = self.env["route.outlet"].sudo()
        locations = (self.location_id | self.location_dest_id).filtered(lambda loc: loc)
        if not locations:
            return outlet_model.browse()
        return outlet_model.search([
            ("outlet_operation_mode", "=", "consignment"),
            ("stock_location_id", "child_of", locations.ids),
        ])

    def _sync_related_consignment_outlet_balances(self):
        outlet_model = self.env["route.outlet"].sudo()
        outlets = outlet_model.browse()
        for picking in self.filtered(lambda p: p.state == "done" and getattr(p.picking_type_id, "code", False) == "internal"):
            outlets |= picking._get_related_consignment_outlets_for_balance_sync()
        if outlets:
            outlets._sync_outlet_stock_balance_records()
        return True

    def button_validate(self):
        result = super().button_validate()
        self.filtered(lambda p: p.state == "done")._sync_related_consignment_outlet_balances()
        return result

    def action_done(self):
        result = super().action_done()
        self.filtered(lambda p: p.state == "done")._sync_related_consignment_outlet_balances()
        return result
