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

    @api.onchange("area_id")
    def _onchange_area_id(self):
        for rec in self:
            rec.outlet_ids = [(5, 0, 0)]

    def action_add_selected_outlets(self):
        self.ensure_one()

        if not self.plan_id:
            raise UserError(_("Route Plan is required."))

        if not self.area_id:
            raise UserError(_("Please select an area."))

        if not self.outlet_ids:
            raise UserError(_("Please select at least one outlet."))

        existing_outlet_ids = self.plan_id.line_ids.mapped("outlet_id").ids
        duplicate_outlets = self.outlet_ids.filtered(lambda o: o.id in existing_outlet_ids)
        if duplicate_outlets:
            raise ValidationError(
                _(
                    "Some selected outlets are already added to this route plan: %s"
                )
                % ", ".join(duplicate_outlets.mapped("display_name"))
            )

        next_sequence = max(self.plan_id.line_ids.mapped("sequence") or [0]) + 10

        vals_list = []
        for outlet in self.outlet_ids:
            vals_list.append({
                "plan_id": self.plan_id.id,
                "sequence": next_sequence,
                "area_id": self.area_id.id,
                "outlet_id": outlet.id,
            })
            next_sequence += 10

        self.env["route.plan.line"].create(vals_list)

        return {"type": "ir.actions.act_window_close"}
