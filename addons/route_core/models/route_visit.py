from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _name = "route.visit"
    _description = "Route Visit"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(
        string="Visit Reference",
        required=True,
        copy=False,
        readonly=True,
        default="New",
        tracking=True,
    )
    date = fields.Date(
        string="Visit Date",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    outlet_id = fields.Many2one(
        "route.outlet",
        string="Outlet",
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        tracking=True,
    )
    area_id = fields.Many2one(
        "route.area",
        string="Area",
        tracking=True,
    )
    vehicle_id = fields.Many2one(
        "route.vehicle",
        string="Vehicle",
        tracking=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
    )
    notes = fields.Text(string="Notes")
    no_sale_reason = fields.Text(
        string="Reason for Ending Without Sale",
        readonly=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )
    start_datetime = fields.Datetime(
        string="Start DateTime",
        readonly=True,
        tracking=True,
    )
    end_datetime = fields.Datetime(
        string="End DateTime",
        readonly=True,
        tracking=True,
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Sale Order",
        readonly=True,
        copy=False,
        tracking=True,
    )
    sale_order_count = fields.Integer(
        string="Sale Order Count",
        compute="_compute_sale_order_count",
    )

    @api.depends("sale_order_id")
    def _compute_sale_order_count(self):
        for rec in self:
            rec.sale_order_count = 1 if rec.sale_order_id else 0

    def _get_outlet_commission_rate_value(self, outlet):
        """Support both field names:
        - commission_rate
        - default_commission_rate
        """
        if not outlet:
            return 0.0

        if "commission_rate" in outlet._fields:
            return outlet.commission_rate or 0.0

        if "default_commission_rate" in outlet._fields:
            return outlet.default_commission_rate or 0.0

        return 0.0

    @api.onchange("outlet_id")
    def _onchange_outlet_id(self):
        for rec in self:
            if rec.outlet_id:
                rec.area_id = rec.outlet_id.area_id
                if rec.outlet_id.partner_id:
                    rec.partner_id = rec.outlet_id.partner_id

                if "commission_rate" in rec._fields:
                    rec.commission_rate = rec._get_outlet_commission_rate_value(rec.outlet_id)

    def _sync_plan_line_state(self):
        plan_lines = self.env["route.plan.line"].search([("visit_id", "in", self.ids)])
        for line in plan_lines:
            if line.visit_id.state == "done":
                line.state = "visited"
            elif line.visit_id.state == "cancel":
                line.state = "skipped"
            else:
                line.state = "pending"

    def _get_plan_line(self):
        self.ensure_one()
        return self.env["route.plan.line"].search([("visit_id", "=", self.id)], limit=1)


    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("route_plan_allow_visit_create"):
            raise UserError(
                _(
                    "Route Visits cannot be created manually. "
                    "They must be generated from Route Plan."
                )
            )

        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("route.visit") or "New"

            outlet_id = vals.get("outlet_id")
            if outlet_id:
                outlet = self.env["route.outlet"].browse(outlet_id)
                if outlet.exists():
                    if not vals.get("area_id") and outlet.area_id:
                        vals["area_id"] = outlet.area_id.id
                    if not vals.get("partner_id") and outlet.partner_id:
                        vals["partner_id"] = outlet.partner_id.id

                    if "commission_rate" in self._fields and not vals.get("commission_rate"):
                        vals["commission_rate"] = self._get_outlet_commission_rate_value(outlet)

        records = super().create(vals_list)
        records._sync_plan_line_state()
        return records

    def write(self, vals):
        if self.env.context.get("route_visit_force_write"):
            result = super().write(vals)
            self._sync_plan_line_state()
            return result

        allowed_when_locked = {
            "message_follower_ids",
            "message_partner_ids",
            "message_ids",
            "activity_ids",
            "activity_state",
            "activity_type_id",
            "activity_user_id",
            "activity_date_deadline",
            "message_main_attachment_id",
            "__last_update",
            "write_date",
            "write_uid",
        }

        for rec in self:
            if rec.state in ("done", "cancel"):
                disallowed_keys = set(vals.keys()) - allowed_when_locked
                if disallowed_keys:
                    raise UserError(
                        _(
                            "You cannot modify a visit that is Done or Cancelled. "
                            "Please reset it first if changes are needed."
                        )
                    )

        if vals.get("outlet_id"):
            outlet = self.env["route.outlet"].browse(vals["outlet_id"])
            if outlet.exists():
                if not vals.get("area_id") and outlet.area_id:
                    vals["area_id"] = outlet.area_id.id
                if not vals.get("partner_id") and outlet.partner_id:
                    vals["partner_id"] = outlet.partner_id.id

                if "commission_rate" in self._fields and not vals.get("commission_rate"):
                    vals["commission_rate"] = self._get_outlet_commission_rate_value(outlet)

        result = super().write(vals)
        self._sync_plan_line_state()
        return result

    def action_start_visit(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only draft visits can be started."))
            if not rec.outlet_id:
                raise UserError(_("Please select an outlet before starting the visit."))
            if not rec.vehicle_id:
                raise UserError(_("Please select a vehicle before starting the visit."))

            rec.write({
                "state": "in_progress",
                "start_datetime": fields.Datetime.now(),
                "end_datetime": False,
                "no_sale_reason": False,
            })

    def _prepare_sale_order_line_vals(self):
        self.ensure_one()
        line_vals = []

        sale_lines = self.line_ids.filtered(
            lambda l: l.product_id and (l.sold_qty or 0.0) > 0
        )

        for line in sale_lines:
            line_vals.append((0, 0, {
                "product_id": line.product_id.id,
                "name": line.product_id.display_name,
                "product_uom_qty": line.sold_qty,
                "price_unit": line.unit_price or line.product_id.lst_price or 0.0,
            }))

        return line_vals

    def _sync_sale_order_lines(self, sale_order):
        self.ensure_one()

        if sale_order.state not in ("draft", "sent"):
            raise UserError(
                _(
                    "The linked Sale Order is already confirmed. "
                    "Reset or cancel it first if you need to rebuild its lines from the visit."
                )
            )

        line_vals = self._prepare_sale_order_line_vals()
        if not line_vals:
            raise UserError(_("No sold quantities were found to create sale order lines."))

        sale_order.order_line.unlink()
        sale_order.write({"order_line": line_vals})

    def _prepare_sale_order_vals(self):
        self.ensure_one()

        vals = {
            "partner_id": self.partner_id.id,
            "user_id": self.user_id.id,
            "origin": self.name,
            "order_line": self._prepare_sale_order_line_vals(),
        }

        if "company_id" in self.env["sale.order"]._fields:
            vals["company_id"] = self.env.company.id

        return vals

    def _get_sale_order_form_action(self, sale_order):
        action = self.env.ref("sale.action_orders").read()[0]
        action["res_id"] = sale_order.id
        action["views"] = [(self.env.ref("sale.view_order_form").id, "form")]
        action["context"] = dict(self.env.context, route_visit_id=self.id)
        return action

    def action_create_sale_order(self):
        self.ensure_one()

        if self.state != "in_progress":
            raise UserError(_("You can only create a sale order when the visit is in progress."))

        if not self.partner_id:
            raise UserError(_("Please set a customer on the visit before creating a sale order."))

        if not self.line_ids.filtered(lambda l: (l.sold_qty or 0.0) > 0):
            raise UserError(_("There are no sold quantities on this visit to create a sale order."))

        if self.sale_order_id:
            self._sync_sale_order_lines(self.sale_order_id)
            self.sale_order_id.action_confirm()
            return self._get_sale_order_form_action(self.sale_order_id)

        sale_order = self.env["sale.order"].create(self._prepare_sale_order_vals())
        self.sale_order_id = sale_order.id
        sale_order.action_confirm()

        return self._get_sale_order_form_action(sale_order)

    def action_view_sale_order(self):
        self.ensure_one()

        if not self.sale_order_id:
            raise UserError(_("There is no sale order linked to this visit."))

        return self._get_sale_order_form_action(self.sale_order_id)

    def action_end_visit(self):
        self.ensure_one()

        if self.state != "in_progress":
            raise UserError(_("Only visits in progress can be ended."))

        if self.sale_order_id and self.sale_order_id.state in ("draft", "sent"):
            raise UserError(
                _(
                    "The linked Sale Order is still not confirmed. "
                    "Please confirm it first or end the visit without sale using the wizard."
                )
            )

        if self.sale_order_id:
            self.with_context(route_visit_force_write=True).write({
                "state": "done",
                "end_datetime": fields.Datetime.now(),
            })
            return True

        return {
            "type": "ir.actions.act_window",
            "name": _("End Visit"),
            "res_model": "route.visit.end.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_visit_id": self.id,
            },
        }

    def action_cancel(self):
        for rec in self:
            if rec.state == "done":
                raise UserError(_("You cannot cancel a completed visit."))
            rec.with_context(route_visit_force_write=True).write({"state": "cancel"})

    def action_reset_to_draft(self):
        for rec in self:
            rec.with_context(route_visit_force_write=True).write({
                "state": "draft",
                "start_datetime": False,
                "end_datetime": False,
                "sale_order_id": False,
                "no_sale_reason": False,
            })
