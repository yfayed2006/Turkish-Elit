from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class RoutePlanAddAreaOutletsWizard(models.TransientModel):
    _name = "route.plan.add.area.outlets.wizard"
    _description = "Add Area Outlets to Route Plan"

    plan_id = fields.Many2one(
        "route.plan",
        string="Route Plan",
        required=True,
        readonly=True,
    )
    area_id = fields.Many2one(
        "route.area",
        string="Area",
        required=True,
    )
    outlet_ids = fields.Many2many(
        "route.outlet",
        string="Outlets",
        domain="[('area_id', '=', area_id)]",
    )
    available_outlet_ids = fields.Many2many(
        "route.outlet",
        string="Available Outlets",
        compute="_compute_available_outlet_ids",
        help="Outlets matching the route plan salesperson, vehicle, and selected area.",
    )

    @api.depends("plan_id", "plan_id.user_id", "plan_id.vehicle_id", "plan_id.line_ids.outlet_id", "area_id")
    def _compute_available_outlet_ids(self):
        Outlet = self.env["route.outlet"]
        for rec in self:
            if rec.plan_id:
                rec.available_outlet_ids = Outlet.search(
                    rec.plan_id._get_outlet_planning_domain(area=rec.area_id)
                )
            elif rec.area_id:
                rec.available_outlet_ids = Outlet.search([("area_id", "=", rec.area_id.id), ("active", "=", True)])
            else:
                rec.available_outlet_ids = Outlet.search([("active", "=", True)])

    @api.onchange("area_id")
    def _onchange_area_id(self):
        for rec in self:
            rec.outlet_ids = [(5, 0, 0)]
        domain = []
        if self.plan_id:
            domain = self.plan_id._get_outlet_planning_domain(area=self.area_id)
        elif self.area_id:
            domain = [("area_id", "=", self.area_id.id), ("active", "=", True)]
        return {"domain": {"outlet_ids": domain}}

    def _ensure_plan_editable(self):
        self.ensure_one()
        if self.plan_id and self.plan_id.planning_finalized:
            raise UserError(
                _(
                    "You cannot add visits by area after Finalize Daily Plan. "
                    "Please click 'Reopen Daily Plan' first."
                )
            )

    def action_select_all_outlets(self):
        self.ensure_one()
        self._ensure_plan_editable()

        if not self.area_id:
            raise UserError(_("Please select an area first."))

        outlets = self.env["route.outlet"].search(
            self.plan_id._get_outlet_planning_domain(area=self.area_id)
        )
        self.outlet_ids = [(6, 0, outlets.ids)]

        return {
            "type": "ir.actions.act_window",
            "res_model": "route.plan.add.area.outlets.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    def action_clear_selection(self):
        self.ensure_one()
        self._ensure_plan_editable()
        self.outlet_ids = [(5, 0, 0)]

        return {
            "type": "ir.actions.act_window",
            "res_model": "route.plan.add.area.outlets.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    def action_add_selected_outlets(self):
        self.ensure_one()
        self._ensure_plan_editable()

        if not self.plan_id:
            raise UserError(_("Route Plan is required."))

        if not self.area_id:
            raise UserError(_("Please select an area."))

        if not self.outlet_ids:
            raise UserError(_("Please select at least one outlet."))

        allowed_outlets = self.env["route.outlet"].search(
            self.plan_id._get_outlet_planning_domain(area=self.area_id)
        )
        blocked_outlets = self.outlet_ids - allowed_outlets
        if blocked_outlets:
            raise ValidationError(
                _(
                    "Some selected outlets do not match this route plan's salesperson, vehicle, area, "
                    "or are already added: %s"
                )
                % ", ".join(blocked_outlets.mapped("display_name"))
            )

        next_sequence = max(self.plan_id.line_ids.mapped("sequence") or [0]) + 10

        vals_list = []
        for outlet in self.outlet_ids:
            vals_list.append({
                "plan_id": self.plan_id.id,
                "sequence": next_sequence,
                "area_id": outlet.area_id.id if outlet.area_id else self.area_id.id,
                "outlet_id": outlet.id,
            })
            next_sequence += 10

        self.env["route.plan.line"].create(vals_list)

        return {"type": "ir.actions.act_window_close"}
