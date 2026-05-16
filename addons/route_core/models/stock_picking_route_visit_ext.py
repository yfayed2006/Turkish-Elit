from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    route_visit_id = fields.Many2one(
        "route.visit",
        string="Route Visit",
        index=True,
        copy=False,
        ondelete="set null",
    )
    route_pda_currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=False,
        readonly=True,
    )
    route_pda_return_line_count = fields.Integer(
        string="Lines",
        compute="_compute_route_pda_return_summary",
        store=False,
    )
    route_pda_return_qty = fields.Float(
        string="Returned Qty",
        compute="_compute_route_pda_return_summary",
        store=False,
    )
    route_pda_return_value = fields.Monetary(
        string="Estimated Value",
        currency_field="route_pda_currency_id",
        compute="_compute_route_pda_return_summary",
        store=False,
    )

    @api.depends("move_ids")
    def _compute_route_pda_return_summary(self):
        for picking in self:
            if "move_ids_without_package" in picking._fields:
                moves = picking.move_ids_without_package
            else:
                moves = picking.move_ids
            line_count = 0
            total_qty = 0.0
            total_value = 0.0
            for move in moves:
                line_count += 1
                qty = (getattr(move, "quantity", 0.0) or 0.0) or (move.product_uom_qty or 0.0)
                total_qty += qty
                amount = getattr(move, "route_direct_return_estimated_amount", 0.0) or 0.0
                if not amount and move.product_id:
                    amount = qty * (move.product_id.lst_price or 0.0)
                total_value += amount
            picking.route_pda_return_line_count = line_count
            picking.route_pda_return_qty = total_qty
            picking.route_pda_return_value = total_value

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
            return outlet.action_open_pda_form()
        home = self.env["route.pda.home"].create({})
        home._refresh_dashboard_snapshot()
        view = self.env.ref("route_core.view_route_pda_outlet_center_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": "Customer Profiles",
            "res_model": "route.pda.home",
            "res_id": home.id,
            "view_mode": "form",
            "target": "main",
            "context": {"create": 0, "edit": 0, "delete": 0},
        }
        if view:
            action["views"] = [(view.id, "form")]
        return action

    def _get_route_visit_finish_return_action(self):
        self.ensure_one()
        if not self.env.context.get("route_return_to_finish_summary"):
            return False

        visit = self.route_visit_id.exists() or self.env["route.visit"].browse(self.env.context.get("route_visit_id")).exists()
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
