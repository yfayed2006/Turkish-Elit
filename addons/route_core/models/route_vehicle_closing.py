from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RouteVehicleClosing(models.Model):
    _name = "route.vehicle.closing"
    _description = "Route Vehicle End of Day Closing"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "plan_date desc, id desc"

    name = fields.Char(
        string="Closing Reference",
        required=True,
        copy=False,
        readonly=True,
        default="New",
        tracking=True,
    )
    plan_id = fields.Many2one(
        "route.plan",
        string="Route Plan",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )
    plan_date = fields.Date(
        string="Plan Date",
        related="plan_id.date",
        store=True,
        readonly=True,
    )
    vehicle_id = fields.Many2one(
        "route.vehicle",
        string="Vehicle",
        related="plan_id.vehicle_id",
        store=True,
        readonly=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        related="plan_id.user_id",
        store=True,
        readonly=True,
    )
    planning_finalized = fields.Boolean(
        string="Daily Planning Finalized",
        related="plan_id.planning_finalized",
        readonly=True,
        store=False,
    )
    planning_finalized_datetime = fields.Datetime(
        string="Planning Finalized On",
        related="plan_id.planning_finalized_datetime",
        readonly=True,
        store=False,
    )
    vehicle_location_id = fields.Many2one(
        "stock.location",
        string="Vehicle Location",
        related="vehicle_id.stock_location_id",
        readonly=True,
        store=False,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )
    snapshot_datetime = fields.Datetime(
        string="Snapshot Refreshed On",
        readonly=True,
        copy=False,
    )
    close_datetime = fields.Datetime(
        string="Closed On",
        readonly=True,
        copy=False,
        tracking=True,
    )
    note = fields.Text(string="Notes")
    line_ids = fields.One2many(
        "route.vehicle.closing.line",
        "closing_id",
        string="Closing Lines",
        copy=True,
    )
    line_count = fields.Integer(
        string="Line Count",
        compute="_compute_totals",
        store=False,
    )
    variance_line_count = fields.Integer(
        string="Variance Lines",
        compute="_compute_totals",
        store=False,
    )
    total_system_qty = fields.Float(
        string="System Qty",
        compute="_compute_totals",
        store=False,
    )
    total_counted_qty = fields.Float(
        string="Counted Qty",
        compute="_compute_totals",
        store=False,
    )
    total_variance_qty = fields.Float(
        string="Net Variance Qty",
        compute="_compute_totals",
        store=False,
    )
    total_abs_variance_qty = fields.Float(
        string="Absolute Variance Qty",
        compute="_compute_totals",
        store=False,
    )

    _sql_constraints = [
        (
            "route_vehicle_closing_plan_unique",
            "unique(plan_id)",
            "Only one vehicle closing is allowed for each route plan.",
        ),
    ]

    @api.depends("line_ids", "line_ids.system_qty", "line_ids.counted_qty", "line_ids.variance_qty")
    def _compute_totals(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.variance_line_count = len(
                rec.line_ids.filtered(lambda line: abs(line.variance_qty or 0.0) > 0.0001)
            )
            rec.total_system_qty = sum(rec.line_ids.mapped("system_qty"))
            rec.total_counted_qty = sum(rec.line_ids.mapped("counted_qty"))
            rec.total_variance_qty = sum(rec.line_ids.mapped("variance_qty"))
            rec.total_abs_variance_qty = sum(abs(line.variance_qty or 0.0) for line in rec.line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("route.vehicle.closing") or "New"
        return super().create(vals_list)

    def _open_form_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Vehicle Closing"),
            "res_model": "route.vehicle.closing",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def _get_vehicle_quants(self):
        self.ensure_one()
        vehicle_location = self.vehicle_location_id
        if not vehicle_location:
            raise UserError(_("Please set the vehicle stock location first."))

        return self.env["stock.quant"].search(
            [
                ("location_id", "child_of", vehicle_location.id),
                ("quantity", "!=", 0),
            ],
            order="product_id, lot_id, location_id, id",
        )

    def _build_snapshot_line_vals(self):
        self.ensure_one()
        existing_map = {}
        for line in self.line_ids:
            key = (line.product_id.id, line.lot_id.id or False, line.location_id.id)
            existing_map[key] = {
                "counted_qty": line.counted_qty,
                "note": line.note,
            }

        line_vals = []
        for quant in self._get_vehicle_quants():
            if not quant.product_id:
                continue
            reserved_qty = 0.0
            if "reserved_quantity" in quant._fields:
                reserved_qty = quant.reserved_quantity or 0.0
            system_qty = quant.quantity or 0.0
            available_qty = max(system_qty - reserved_qty, 0.0)
            key = (quant.product_id.id, quant.lot_id.id or False, quant.location_id.id)
            previous = existing_map.get(key, {})
            line_vals.append(
                {
                    "product_id": quant.product_id.id,
                    "location_id": quant.location_id.id,
                    "lot_id": quant.lot_id.id or False,
                    "in_date": quant.in_date,
                    "system_qty": system_qty,
                    "reserved_qty": reserved_qty,
                    "available_qty": available_qty,
                    "counted_qty": previous.get("counted_qty", system_qty),
                    "note": previous.get("note", False),
                }
            )

        line_vals.sort(
            key=lambda vals: (
                self.env["product.product"].browse(vals["product_id"]).display_name or "",
                vals.get("location_id") or 0,
                vals.get("lot_id") or 0,
            )
        )
        return line_vals

    def action_refresh_snapshot(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("You can refresh the vehicle closing snapshot only while it is in draft."))
            line_vals = rec._build_snapshot_line_vals()
            rec.line_ids.unlink()
            if line_vals:
                self.env["route.vehicle.closing.line"].create(
                    [dict(vals, closing_id=rec.id) for vals in line_vals]
                )
            rec.snapshot_datetime = fields.Datetime.now()
        return True

    def action_close_day(self):
        for rec in self:
            if rec.state != "draft":
                continue
            if not rec.vehicle_id:
                raise UserError(_("The closing record is missing a vehicle."))
            if not rec.vehicle_location_id:
                raise UserError(_("Please set the vehicle stock location first."))
            if not rec.line_ids:
                rec.action_refresh_snapshot()
            rec.write(
                {
                    "state": "closed",
                    "close_datetime": fields.Datetime.now(),
                }
            )
            if rec.variance_line_count:
                rec.message_post(
                    body=_(
                        "Vehicle day closed with %(count)s variance line(s). Net variance qty: %(qty).2f"
                    )
                    % {
                        "count": rec.variance_line_count,
                        "qty": rec.total_variance_qty,
                    }
                )
            else:
                rec.message_post(body=_("Vehicle day closed with no stock variance."))
        return True

    def action_reset_to_draft(self):
        self.write(
            {
                "state": "draft",
                "close_datetime": False,
            }
        )
        return True

    def action_cancel(self):
        self.write({"state": "cancelled"})
        return True

    def action_open_route_plan(self):
        self.ensure_one()
        if not self.plan_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Route Plan"),
            "res_model": "route.plan",
            "res_id": self.plan_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_vehicle_stock_snapshot(self):
        self.ensure_one()
        vehicle_location = self.vehicle_location_id
        if not vehicle_location:
            raise UserError(_("Please set the vehicle stock location first."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Vehicle Stock Snapshot"),
            "res_model": "stock.quant",
            "view_mode": "list,form",
            "views": [
                (self.env.ref("route_core.view_route_vehicle_stock_snapshot_list").id, "list"),
                (False, "form"),
            ],
            "search_view_id": self.env.ref("route_core.view_route_vehicle_stock_snapshot_search").id,
            "target": "current",
            "domain": [
                ("location_id", "child_of", vehicle_location.id),
                ("quantity", ">", 0),
            ],
            "context": {
                "search_default_filter_positive_qty": 1,
                "default_location_id": vehicle_location.id,
            },
        }


class RouteVehicleClosingLine(models.Model):
    _name = "route.vehicle.closing.line"
    _description = "Route Vehicle Closing Line"
    _order = "product_id, lot_id, location_id, id"

    closing_id = fields.Many2one(
        "route.vehicle.closing",
        string="Vehicle Closing",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        ondelete="restrict",
    )
    barcode = fields.Char(
        string="Barcode",
        related="product_id.barcode",
        readonly=True,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="UoM",
        related="product_id.uom_id",
        readonly=True,
    )
    location_id = fields.Many2one(
        "stock.location",
        string="Location",
        required=True,
        ondelete="restrict",
    )
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lot/Serial Number",
        ondelete="restrict",
    )
    expiry_date = fields.Datetime(
        string="Expiry Date",
        related="lot_id.expiration_date",
        readonly=True,
    )
    alert_date = fields.Datetime(
        string="Alert Date",
        related="lot_id.alert_date",
        readonly=True,
    )
    in_date = fields.Datetime(string="Incoming Date")
    system_qty = fields.Float(string="System Qty", digits="Product Unit of Measure")
    reserved_qty = fields.Float(string="Reserved Qty", digits="Product Unit of Measure")
    available_qty = fields.Float(string="Available Qty", digits="Product Unit of Measure")
    counted_qty = fields.Float(string="Counted Qty", digits="Product Unit of Measure")
    variance_qty = fields.Float(
        string="Variance Qty",
        compute="_compute_variance",
        store=False,
        digits="Product Unit of Measure",
    )
    variance_status = fields.Selection(
        [
            ("match", "Match"),
            ("short", "Short"),
            ("over", "Over"),
        ],
        string="Variance Status",
        compute="_compute_variance",
        store=False,
    )
    note = fields.Char(string="Note")

    @api.depends("system_qty", "counted_qty")
    def _compute_variance(self):
        for rec in self:
            variance = (rec.counted_qty or 0.0) - (rec.system_qty or 0.0)
            rec.variance_qty = variance
            if abs(variance) <= 0.0001:
                rec.variance_status = "match"
            elif variance < 0:
                rec.variance_status = "short"
            else:
                rec.variance_status = "over"


class RoutePlan(models.Model):
    _inherit = "route.plan"

    vehicle_closing_ids = fields.One2many(
        "route.vehicle.closing",
        "plan_id",
        string="Vehicle Closings",
    )
    vehicle_closing_count = fields.Integer(
        string="Vehicle Closings",
        compute="_compute_vehicle_closing_stats",
        store=False,
    )
    vehicle_closing_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        string="Vehicle Closing Status",
        compute="_compute_vehicle_closing_stats",
        store=False,
    )

    def _compute_vehicle_closing_stats(self):
        for rec in self:
            closings = rec.vehicle_closing_ids.sorted(key=lambda closing: closing.id, reverse=True)
            rec.vehicle_closing_count = len(closings)
            rec.vehicle_closing_state = closings[:1].state if closings else False

    def _get_active_vehicle_closing(self):
        self.ensure_one()
        return self.vehicle_closing_ids.sorted(key=lambda closing: closing.id, reverse=True)[:1]

    def action_open_vehicle_closing(self):
        self.ensure_one()
        if not self.vehicle_id:
            raise UserError(_("Please select a vehicle first."))
        if not getattr(self.vehicle_id, "stock_location_id", False):
            raise UserError(_("Please set the vehicle stock location first."))

        closing = self._get_active_vehicle_closing()
        if not closing:
            closing = self.env["route.vehicle.closing"].create(
                {
                    "plan_id": self.id,
                    "company_id": self.env.company.id,
                    "note": _(
                        "End-of-day vehicle closing. Count the physical stock on the vehicle and compare it with the system stock snapshot."
                    ),
                }
            )
            closing.action_refresh_snapshot()
        return closing._open_form_action()


class RouteLoadingProposal(models.Model):
    _inherit = "route.loading.proposal"

    def action_open_vehicle_closing(self):
        self.ensure_one()
        if not self.plan_id:
            raise UserError(_("This loading proposal is not linked to a route plan."))
        return self.plan_id.action_open_vehicle_closing()
