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
    route_return_to_finish_summary = fields.Boolean(
        string="Return To Visit Finish Summary",
        copy=False,
        default=False,
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


    def action_back_to_outlet_form(self):
        self.ensure_one()
        outlet = False
        outlet_id = self.env.context.get("route_outlet_back_id") or self.env.context.get("default_outlet_id")
        if outlet_id:
            outlet = self.env["route.outlet"].browse(outlet_id).exists()
        if not outlet and getattr(self, "route_direct_return_id", False) and self.route_direct_return_id.outlet_id:
            outlet = self.route_direct_return_id.outlet_id
        if not outlet and getattr(self, "route_visit_id", False) and self.route_visit_id.outlet_id:
            outlet = self.route_visit_id.outlet_id
        if outlet:
            return {
                "type": "ir.actions.act_url",
                "url": f"/route_core/pda/outlet/{outlet.id}",
                "target": "self",
            }
        return {
            "type": "ir.actions.act_url",
            "url": "/route_core/pda/outlet_center",
            "target": "self",
        }

    def _get_route_visit_finish_return_action(self):
        self.ensure_one()
        if not self.route_return_to_finish_summary:
            return False

        visit = self.route_visit_id.exists()
        self.route_return_to_finish_summary = False
        if not visit:
            return False

        if visit.state == "in_progress":
            finish_result = visit.action_end_visit()
            if isinstance(finish_result, dict):
                return finish_result

        if visit.state == "done" and hasattr(visit, "_get_route_visit_finish_summary_action"):
            return visit._get_route_visit_finish_summary_action()

        if hasattr(visit, "_get_pda_form_action"):
            return visit._get_pda_form_action()
        return False

    def _post_validate_route_visit_action(self):
        done_pickings = self.filtered(lambda p: p.state == "done")
        done_pickings._sync_related_consignment_outlet_balances()
        for picking in done_pickings:
            action = picking._get_route_visit_finish_return_action()
            if action:
                return action
        return False

    def button_validate(self):
        result = super().button_validate()
        followup_action = self._post_validate_route_visit_action()
        return followup_action or result

    def action_done(self):
        result = super().action_done()
        followup_action = self._post_validate_route_visit_action()
        return followup_action or result
