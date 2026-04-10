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

    def _route_get_consignment_outlets_to_sync(self):
        outlets = self.env["route.outlet"].sudo().search([
            ("outlet_operation_mode", "=", "consignment"),
            ("stock_location_id", "!=", False),
        ])
        touched_locations = (self.mapped("location_id") | self.mapped("location_dest_id")).filtered(lambda loc: loc)
        if not touched_locations:
            return self.env["route.outlet"]
        return outlets.filtered(lambda outlet: outlet.stock_location_id in touched_locations)

    def _route_sync_consignment_outlet_balances(self):
        outlets = self._route_get_consignment_outlets_to_sync()
        if outlets and hasattr(outlets, "_sync_stock_balances_from_quants"):
            outlets._sync_stock_balances_from_quants()
        return True

    def button_validate(self):
        result = super().button_validate()
        done_pickings = self.filtered(lambda picking: picking.state == "done")
        if done_pickings:
            done_pickings._route_sync_consignment_outlet_balances()
        return result
