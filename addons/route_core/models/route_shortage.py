from odoo import _, api, fields, models


class RouteShortage(models.Model):
    _name = "route.shortage"
    _description = "Route Shortage"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(
        string="Shortage Reference",
        required=True,
        copy=False,
        readonly=True,
        default="New",
        tracking=True,
    )
    date = fields.Date(
        string="Shortage Date",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        readonly=True,
        store=False,
    )
    source_visit_id = fields.Many2one(
        "route.visit",
        string="Source Visit",
        ondelete="set null",
        tracking=True,
    )
    outlet_id = fields.Many2one(
        "route.outlet",
        string="Outlet",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        ondelete="set null",
        tracking=True,
    )
    area_id = fields.Many2one(
        "route.area",
        string="Area",
        ondelete="set null",
        tracking=True,
    )
    vehicle_id = fields.Many2one(
        "route.vehicle",
        string="Vehicle",
        ondelete="set null",
        tracking=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        ondelete="set null",
        tracking=True,
    )
    planned_date = fields.Date(
        string="Planned Follow-up Date",
        tracking=True,
        help="Optional planning date for following up these shortages in a future visit.",
    )
    state = fields.Selection(
        [
            ("open", "Open"),
            ("planned", "Planned"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        string="Status",
        default="open",
        required=True,
        tracking=True,
    )
    note = fields.Text(string="Notes")
    line_ids = fields.One2many(
        "route.shortage.line",
        "shortage_id",
        string="Shortage Lines",
        copy=True,
    )
    line_count = fields.Integer(
        string="Line Count",
        compute="_compute_shortage_stats",
        store=False,
    )
    product_count = fields.Integer(
        string="Product Count",
        compute="_compute_shortage_stats",
        store=False,
    )
    total_missing_qty = fields.Float(
        string="Total Missing Qty",
        compute="_compute_shortage_stats",
        store=False,
    )
    total_remaining_qty = fields.Float(
        string="Remaining Qty",
        compute="_compute_shortage_stats",
        store=False,
    )

    @api.depends("line_ids.product_id", "line_ids.qty_missing", "line_ids.qty_remaining")
    def _compute_shortage_stats(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.product_count = len(rec.line_ids.filtered(lambda l: l.product_id))
            rec.total_missing_qty = sum(rec.line_ids.mapped("qty_missing"))
            rec.total_remaining_qty = sum(rec.line_ids.mapped("qty_remaining"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("route.shortage") or "New"
        return super().create(vals_list)

    def action_mark_planned(self):
        for rec in self:
            rec.state = "planned"

    def action_mark_done(self):
        for rec in self:
            rec.state = "done"

    def action_reopen(self):
        for rec in self:
            rec.state = "open"

    def action_cancel(self):
        for rec in self:
            rec.state = "cancel"

    def action_view_source_visit(self):
        self.ensure_one()
        if not self.source_visit_id:
            return False
        return self.source_visit_id._get_pda_form_action()


class RouteShortageLine(models.Model):
    _name = "route.shortage.line"
    _description = "Route Shortage Line"
    _order = "shortage_id, id"

    shortage_id = fields.Many2one(
        "route.shortage",
        string="Shortage",
        required=True,
        ondelete="cascade",
        index=True,
    )
    shortage_state = fields.Selection(
        related="shortage_id.state",
        string="Shortage Status",
        store=False,
        readonly=True,
    )
    company_id = fields.Many2one(
        related="shortage_id.company_id",
        string="Company",
        store=False,
        readonly=True,
    )
    currency_id = fields.Many2one(
        related="shortage_id.currency_id",
        string="Currency",
        store=False,
        readonly=True,
    )
    outlet_id = fields.Many2one(
        related="shortage_id.outlet_id",
        string="Outlet",
        store=False,
        readonly=True,
    )
    source_visit_line_id = fields.Many2one(
        "route.visit.line",
        string="Source Visit Line",
        ondelete="set null",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        ondelete="restrict",
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="UoM",
        related="product_id.uom_id",
        readonly=True,
        store=False,
    )
    qty_sold = fields.Float(string="Sold Qty", readonly=True)
    qty_supplied = fields.Float(string="Supplied Qty", readonly=True)
    qty_missing = fields.Float(string="Missing Qty", required=True, default=0.0)
    qty_done = fields.Float(string="Fulfilled Qty", default=0.0)
    qty_remaining = fields.Float(
        string="Remaining Qty",
        compute="_compute_qty_remaining",
        store=True,
    )
    unit_price = fields.Float(string="Unit Price", default=0.0)
    missing_value = fields.Monetary(
        string="Missing Value",
        currency_field="currency_id",
        compute="_compute_values",
        store=True,
    )
    remaining_value = fields.Monetary(
        string="Remaining Value",
        currency_field="currency_id",
        compute="_compute_values",
        store=True,
    )
    note = fields.Char(string="Note")
    state = fields.Selection(
        [
            ("open", "Open"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        string="Line Status",
        default="open",
        required=True,
    )

    @api.depends("qty_missing", "qty_done", "state")
    def _compute_qty_remaining(self):
        for rec in self:
            if rec.state == "cancel":
                rec.qty_remaining = 0.0
            else:
                rec.qty_remaining = max((rec.qty_missing or 0.0) - (rec.qty_done or 0.0), 0.0)

    @api.depends("qty_missing", "qty_remaining", "unit_price")
    def _compute_values(self):
        for rec in self:
            price = rec.unit_price or 0.0
            rec.missing_value = (rec.qty_missing or 0.0) * price
            rec.remaining_value = (rec.qty_remaining or 0.0) * price

    @api.onchange("qty_done", "qty_missing")
    def _onchange_progress_state(self):
        for rec in self:
            if rec.state == "cancel":
                continue
            if (rec.qty_done or 0.0) >= (rec.qty_missing or 0.0) and (rec.qty_missing or 0.0) > 0:
                rec.state = "done"
            else:
                rec.state = "open"

    @api.onchange("state")
    def _onchange_state(self):
        for rec in self:
            if rec.state == "cancel":
                rec.qty_done = 0.0
            elif rec.state == "done" and (rec.qty_missing or 0.0) > 0:
                rec.qty_done = rec.qty_missing


class RouteVisit(models.Model):
    _inherit = "route.visit"

    shortage_count = fields.Integer(
        string="Shortages",
        compute="_compute_shortage_count",
        store=False,
    )

    def _compute_shortage_count(self):
        shortage_model = self.env["route.shortage"]
        for rec in self:
            rec.shortage_count = shortage_model.search_count([("source_visit_id", "=", rec.id)])

    def action_view_shortages(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_shortage").read()[0]
        action["domain"] = [("source_visit_id", "=", self.id)]
        action["context"] = dict(self.env.context, default_source_visit_id=self.id, default_outlet_id=self.outlet_id.id)
        return action

    def _get_shortage_candidate_lines(self):
        self.ensure_one()
        return self.line_ids.filtered(
            lambda l: l.product_id and max((l.sold_qty or 0.0) - (l.supplied_qty or 0.0), 0.0) > 0
        )

    def _prepare_shortage_header_vals(self):
        self.ensure_one()
        return {
            "date": self.date or fields.Date.context_today(self),
            "company_id": self.company_id.id,
            "source_visit_id": self.id,
            "outlet_id": self.outlet_id.id,
            "partner_id": self.partner_id.id if self.partner_id else False,
            "area_id": self.area_id.id if self.area_id else False,
            "vehicle_id": self.vehicle_id.id if self.vehicle_id else False,
            "user_id": self.user_id.id if self.user_id else False,
            "state": "open",
        }

    def _prepare_shortage_line_vals(self, visit_line):
        self.ensure_one()
        shortage_qty = max((visit_line.sold_qty or 0.0) - (visit_line.supplied_qty or 0.0), 0.0)
        return {
            "source_visit_line_id": visit_line.id,
            "product_id": visit_line.product_id.id,
            "qty_sold": visit_line.sold_qty or 0.0,
            "qty_supplied": visit_line.supplied_qty or 0.0,
            "qty_missing": shortage_qty,
            "qty_done": 0.0,
            "unit_price": visit_line.unit_price or 0.0,
            "note": _("Generated from visit %s") % (self.name,),
            "state": "open",
        }

    def _sync_shortages_from_visit(self):
        shortage_model = self.env["route.shortage"]
        for rec in self:
            candidate_lines = rec._get_shortage_candidate_lines()
            shortage = shortage_model.search([(
                "source_visit_id", "=", rec.id
            )], limit=1)

            if not candidate_lines:
                if shortage and shortage.state not in ("done", "cancel"):
                    shortage.line_ids.unlink()
                    shortage.state = "done"
                    shortage.note = (shortage.note or "") + ("\n" if shortage.note else "") + _("Automatically closed because no remaining shortages were detected.")
                continue

            if not shortage:
                shortage = shortage_model.create(rec._prepare_shortage_header_vals())
            else:
                shortage.write(rec._prepare_shortage_header_vals())
                shortage.line_ids.unlink()

            line_commands = [(0, 0, rec._prepare_shortage_line_vals(line)) for line in candidate_lines]
            shortage.write({"line_ids": line_commands, "state": "open"})

    def action_end_visit(self):
        result = super().action_end_visit()
        for rec in self:
            if rec.state == "done":
                rec._sync_shortages_from_visit()
        return result
