from odoo import api, fields, models


class RouteVisit(models.Model):
    _name = "route.visit"
    _description = "Route Visit"
    _order = "id desc"

    name = fields.Char(
        string="Visit Reference",
        required=True,
        readonly=True,
        copy=False,
        default="New",
    )
    date = fields.Date(string="Visit Date")
    notes = fields.Text(string="Notes")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        string="Status",
        default="draft",
    )
    user_id = fields.Many2one("res.users", string="Salesperson")
    partner_id = fields.Many2one("res.partner", string="Customer")
    start_datetime = fields.Datetime(string="Start Time", readonly=True)
    end_datetime = fields.Datetime(string="End Time", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("route.visit.seq") or "New"
        return super().create(vals_list)

    def action_start_visit(self):
        for rec in self:
            rec.write({
                "state": "in_progress",
                "start_datetime": fields.Datetime.now(),
            })

    def action_end_visit(self):
        for rec in self:
            rec.write({
                "state": "done",
                "end_datetime": fields.Datetime.now(),
            })

    def action_cancel_visit(self):
        for rec in self:
            rec.state = "cancel"

    def action_reset_to_draft(self):
        for rec in self:
            rec.write({
                "state": "draft",
                "start_datetime": False,
                "end_datetime": False,
            })
