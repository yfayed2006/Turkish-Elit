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
        store=False,
        readonly=True,
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

    source_location_id = fields.Many2one(
        "stock.location",
        string="Source Location",
        tracking=True,
        copy=False,
    )
    destination_location_id = fields.Many2one(
        "stock.location",
        string="Destination Location",
        tracking=True,
        copy=False,
    )

    near_expiry_threshold_days = fields.Integer(
        string="Near Expiry Threshold Days",
        default=60,
        tracking=True,
        help="If expiry is within this number of days, the line is treated as near expiry.",
    )

    collection_skip_reason = fields.Text(
        string="Collection Skip Reason",
        tracking=True,
        copy=False,
    )
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

    visit_process_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("checked_in", "Checked In"),
            ("counting", "Counting"),
            ("reconciled", "Reconciled"),
            ("collection_done", "Collection Done"),
            ("ready_to_close", "Ready To Close"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        string="Visit Process State",
        default="draft",
        tracking=True,
        copy=False,
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

    line_ids = fields.One2many(
        "route.visit.line",
        "visit_id",
        string="Visit Lines",
    )
    payment_ids = fields.One2many(
        "route.visit.payment",
        "visit_id",
        string="Payments",
    )

    net_due_amount = fields.Monetary(
        string="Net Due Amount",
        currency_field="currency_id",
        compute="_compute_payment_totals",
        store=False,
    )
    collected_amount = fields.Monetary(
        string="Collected Amount",
        currency_field="currency_id",
        compute="_compute_payment_totals",
        store=False,
    )
    remaining_due_amount = fields.Monetary(
        string="Remaining Due Amount",
        currency_field="currency_id",
        compute="_compute_payment_totals",
        store=False,
    )

    has_returns = fields.Boolean(
        string="Has Returns",
        default=False,
        tracking=True,
        copy=False,
    )
    returns_step_done = fields.Boolean(
        string="Returns Step Done",
        default=False,
        tracking=True,
        copy=False,
    )
    has_refill = fields.Boolean(
        string="Has Refill",
        default=False,
        tracking=True,
        copy=False,
    )
    has_pending_refill = fields.Boolean(
        string="Has Pending Refill",
        default=False,
        tracking=True,
        copy=False,
    )
    no_refill = fields.Boolean(
        string="No Refill",
        default=False,
        tracking=True,
        copy=False,
    )

    refill_datetime = fields.Datetime(
        string="Refill Datetime",
        tracking=True,
        copy=False,
    )
    refill_backorder_id = fields.Many2one(
        "route.refill.backorder",
        string="Refill Backorder",
        copy=False,
    )
    refill_picking_id = fields.Many2one(
        "stock.picking",
        string="Refill Transfer",
        copy=False,
    )
    refill_picking_count = fields.Integer(
        string="Refill Transfer Count",
        compute="_compute_refill_picking_count",
        store=False,
    )

    return_picking_ids = fields.One2many(
        "stock.picking",
        "route_visit_id",
        string="Return Transfers",
    )
    return_picking_count = fields.Integer(
        string="Return Pickings",
        compute="_compute_return_picking_count",
        store=False,
    )

    near_expiry_line_count = fields.Integer(
        string="Near Expiry Lines",
        compute="_compute_near_expiry_status",
        store=True,
    )
    pending_near_expiry_line_count = fields.Integer(
        string="Pending Near Expiry Lines",
        compute="_compute_near_expiry_status",
        store=True,
    )
    has_pending_near_expiry = fields.Boolean(
        string="Has Pending Near Expiry",
        compute="_compute_near_expiry_status",
        store=True,
    )


    visit_mode = fields.Selection(
        [
            ("regular", "Regular Visit"),
            ("collection_first", "Collection First"),
            ("refill_first", "Refill First"),
            ("audit_only", "Audit Only"),
        ],
        string="Visit Mode",
        default="regular",
        required=True,
        tracking=True,
        copy=False,
    )
    visit_mode_recommendation = fields.Selection(
        [
            ("regular", "Regular Visit"),
            ("collection_first", "Collection First"),
            ("refill_first", "Refill First"),
            ("audit_only", "Audit Only"),
        ],
        string="Recommended Visit Mode",
        compute="_compute_visit_command_header",
        store=False,
    )
    collection_priority = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        string="Collection Priority",
        compute="_compute_visit_command_header",
        store=False,
    )
    outlet_current_due_amount = fields.Monetary(
        string="Current Due",
        currency_field="currency_id",
        compute="_compute_visit_command_header",
        store=False,
    )
    outlet_open_shortage_count = fields.Integer(
        string="Open Shortages",
        compute="_compute_visit_command_header",
        store=False,
    )
    outlet_near_expiry_count = fields.Integer(
        string="Near Expiry",
        compute="_compute_visit_command_header",
        store=False,
    )
    outlet_summary_alert_level = fields.Selection(
        [("normal", "Normal"), ("warning", "Needs Follow-up"), ("critical", "Critical")],
        string="Outlet Alert Level",
        compute="_compute_visit_command_header",
        store=False,
    )
    outlet_decision_flags_html = fields.Html(
        string="Decision Flags",
        compute="_compute_visit_command_header",
        sanitize=False,
    )


    def _get_collection_priority_value(self, outlet):
        if not outlet:
            return "low"

        aging_90_plus = getattr(outlet, "aging_90_plus_amount", 0.0) or 0.0
        aging_61_90 = getattr(outlet, "aging_61_90_amount", 0.0) or 0.0
        current_due = getattr(outlet, "current_due_amount", 0.0) or 0.0
        collection_status = getattr(outlet, "collection_status", False)
        deferred_count = getattr(outlet, "deferred_payment_count", 0) or 0

        if aging_90_plus > 0:
            return "critical"
        if aging_61_90 > 0 or collection_status == "weak":
            return "high"
        if current_due > 0 or collection_status == "warning" or deferred_count > 0:
            return "medium"
        return "low"

    def _get_recommended_visit_mode_value(self, outlet, collection_priority):
        if not outlet:
            return "regular"

        refill_needed_count = getattr(outlet, "refill_needed_count", 0) or 0
        open_shortage_count = getattr(outlet, "open_shortage_count", 0) or 0
        near_expiry_count = getattr(outlet, "near_expiry_product_count", 0) or 0
        expired_count = getattr(outlet, "expired_product_count", 0) or 0

        if collection_priority in ("high", "critical"):
            return "collection_first"
        if refill_needed_count > 0 or open_shortage_count > 0:
            return "refill_first"
        if near_expiry_count > 0 or expired_count > 0:
            return "audit_only"
        return "regular"

    def _build_visit_command_flags_html(self, outlet, collection_priority, open_shortages, near_expiry, pending_decisions):
        def _badge(label, style):
            return (
                '<span style="display:inline-flex;align-items:center;white-space:nowrap;'
                'margin:0 6px 6px 0;padding:4px 10px;border-radius:999px;'
                'font-weight:600;font-size:13px;line-height:1.35;%s">%s</span>'
            ) % (style, label)

        badges = []
        alert_level = getattr(outlet, "summary_alert_level", "normal") if outlet else "normal"

        if collection_priority == "critical":
            badges.append(_badge("Critical Debt", "background:#f8d7da;color:#b02a37;"))
        elif collection_priority == "high":
            badges.append(_badge("Collect First", "background:#fde2e4;color:#b02a37;"))
        elif collection_priority == "medium":
            badges.append(_badge("Collection Follow-up", "background:#fff3cd;color:#8a6d1d;"))

        if open_shortages > 0:
            badges.append(_badge("Open Shortages", "background:#e2e3ff;color:#3d3d9b;"))

        if near_expiry > 0:
            badges.append(_badge("Near Expiry Risk", "background:#f6e7b0;color:#8a6d1d;"))

        if pending_decisions > 0:
            badges.append(_badge("Pending Expiry Decision", "background:#ffe5d0;color:#b54708;"))

        if alert_level == "critical":
            badges.append(_badge("Visit Now", "background:#f8d7da;color:#b02a37;"))
        elif alert_level == "warning":
            badges.append(_badge("Needs Follow-up", "background:#fff3cd;color:#8a6d1d;"))

        if not badges:
            badges.append(_badge("Normal", "background:#d1f7d6;color:#1e7e34;"))

        return "".join(badges)

    @api.depends(
        "outlet_id",
        "outlet_id.current_due_amount",
        "outlet_id.open_shortage_count",
        "outlet_id.near_expiry_product_count",
        "outlet_id.summary_alert_level",
        "outlet_id.aging_61_90_amount",
        "outlet_id.aging_90_plus_amount",
        "outlet_id.collection_status",
        "outlet_id.deferred_payment_count",
        "outlet_id.refill_needed_count",
        "outlet_id.expired_product_count",
        "pending_near_expiry_line_count",
        "has_pending_near_expiry",
    )
    def _compute_visit_command_header(self):
        for rec in self:
            outlet = rec.outlet_id
            current_due = (getattr(outlet, "current_due_amount", 0.0) or 0.0) if outlet else 0.0
            open_shortages = (getattr(outlet, "open_shortage_count", 0) or 0) if outlet else 0
            near_expiry = (getattr(outlet, "near_expiry_product_count", 0) or 0) if outlet else 0

            priority = rec._get_collection_priority_value(outlet)
            recommendation = rec._get_recommended_visit_mode_value(outlet, priority)

            rec.collection_priority = priority
            rec.visit_mode_recommendation = recommendation
            rec.outlet_current_due_amount = current_due
            rec.outlet_open_shortage_count = open_shortages
            rec.outlet_near_expiry_count = near_expiry
            rec.outlet_summary_alert_level = getattr(outlet, "summary_alert_level", "normal") if outlet else "normal"
            rec.outlet_decision_flags_html = rec._build_visit_command_flags_html(
                outlet,
                priority,
                open_shortages,
                near_expiry,
                rec.pending_near_expiry_line_count or 0,
            )

    @api.depends("sale_order_id")
    def _compute_sale_order_count(self):
        for rec in self:
            rec.sale_order_count = 1 if rec.sale_order_id else 0

    @api.depends("line_ids.sold_qty", "line_ids.unit_price", "payment_ids.amount", "payment_ids.state")
    def _compute_payment_totals(self):
        for rec in self:
            total_sales = 0.0
            for line in rec.line_ids:
                sold_qty = getattr(line, "sold_qty", 0.0) or 0.0
                unit_price = getattr(line, "unit_price", 0.0) or 0.0
                total_sales += sold_qty * unit_price

            confirmed_payments = rec.payment_ids.filtered(lambda p: p.state == "confirmed") if rec.payment_ids else rec.payment_ids
            total_collected = sum(confirmed_payments.mapped("amount")) if confirmed_payments else 0.0

            rec.net_due_amount = total_sales
            rec.collected_amount = total_collected
            rec.remaining_due_amount = max((total_sales or 0.0) - (total_collected or 0.0), 0.0)

    def _compute_refill_picking_count(self):
        for rec in self:
            rec.refill_picking_count = 1 if rec.refill_picking_id else 0

    def _compute_return_picking_count(self):
        for rec in self:
            rec.return_picking_count = len(rec.return_picking_ids)

    @api.depends(
        "line_ids.is_near_expiry",
        "line_ids.near_expiry_action_state",
    )
    def _compute_near_expiry_status(self):
        for rec in self:
            near_lines = rec.line_ids.filtered(lambda l: l.is_near_expiry)
            pending_lines = near_lines.filtered(
                lambda l: l.near_expiry_action_state == "pending"
            )

            rec.near_expiry_line_count = len(near_lines)
            rec.pending_near_expiry_line_count = len(pending_lines)
            rec.has_pending_near_expiry = bool(pending_lines)

    def _get_outlet_commission_rate_value(self, outlet):
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
                if hasattr(rec.vehicle_id, "stock_location_id") and rec.vehicle_id.stock_location_id:
                    rec.source_location_id = rec.vehicle_id.stock_location_id
                if hasattr(rec.outlet_id, "stock_location_id") and rec.outlet_id.stock_location_id:
                    rec.destination_location_id = rec.outlet_id.stock_location_id

                if "commission_rate" in rec._fields:
                    rec.commission_rate = rec._get_outlet_commission_rate_value(rec.outlet_id)

                recommended_mode = rec._get_recommended_visit_mode_value(
                    rec.outlet_id,
                    rec._get_collection_priority_value(rec.outlet_id),
                )
                if not rec.visit_mode or rec.visit_mode == "regular":
                    rec.visit_mode = recommended_mode

    @api.onchange("vehicle_id")
    def _onchange_vehicle_id_set_source_location(self):
        for rec in self:
            if rec.vehicle_id and hasattr(rec.vehicle_id, "stock_location_id"):
                rec.source_location_id = rec.vehicle_id.stock_location_id

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

    def _raise_pending_near_expiry_error(self):
        self.ensure_one()

        pending_lines = self.line_ids.filtered(
            lambda l: l.near_expiry_action_state == "pending"
        )
        if not pending_lines:
            return

        product_names = pending_lines.mapped("product_id.display_name")
        product_lines = "\n- " + "\n- ".join(product_names[:10])

        raise UserError(_(
            "You still have Near Expiry items pending a decision.\n"
            "Please either:\n"
            "- set Return Route = Near Expiry Stock with return quantity, or\n"
            "- mark the line as Keep Near Expiry.\n"
            "\nPending items:%s"
        ) % product_lines)

    def _phase0_notification(self, title, message, notif_type="success", sticky=False):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": notif_type,
                "sticky": sticky,
            },
        }

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
            vehicle_id = vals.get("vehicle_id")

            if outlet_id:
                outlet = self.env["route.outlet"].browse(outlet_id)
                if outlet.exists():
                    if not vals.get("area_id") and outlet.area_id:
                        vals["area_id"] = outlet.area_id.id
                    if not vals.get("partner_id") and outlet.partner_id:
                        vals["partner_id"] = outlet.partner_id.id
                    if not vals.get("company_id") and outlet.company_id:
                        vals["company_id"] = outlet.company_id.id
                    if not vals.get("destination_location_id") and hasattr(outlet, "stock_location_id") and outlet.stock_location_id:
                        vals["destination_location_id"] = outlet.stock_location_id.id

                    if "commission_rate" in self._fields and not vals.get("commission_rate"):
                        vals["commission_rate"] = self._get_outlet_commission_rate_value(outlet)

            if vehicle_id:
                vehicle = self.env["route.vehicle"].browse(vehicle_id)
                if vehicle.exists():
                    if not vals.get("source_location_id") and hasattr(vehicle, "stock_location_id") and vehicle.stock_location_id:
                        vals["source_location_id"] = vehicle.stock_location_id.id

            vals.setdefault("company_id", self.env.company.id)
            vals.setdefault("visit_process_state", "draft")
            vals.setdefault("near_expiry_threshold_days", 60)
            vals.setdefault("has_returns", False)
            vals.setdefault("returns_step_done", False)
            vals.setdefault("has_refill", False)
            vals.setdefault("has_pending_refill", False)
            vals.setdefault("no_refill", False)

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
                if not vals.get("company_id") and outlet.company_id:
                    vals["company_id"] = outlet.company_id.id
                if not vals.get("destination_location_id") and hasattr(outlet, "stock_location_id") and outlet.stock_location_id:
                    vals["destination_location_id"] = outlet.stock_location_id.id

                if "commission_rate" in self._fields and not vals.get("commission_rate"):
                    vals["commission_rate"] = self._get_outlet_commission_rate_value(outlet)

        if vals.get("vehicle_id"):
            vehicle = self.env["route.vehicle"].browse(vals["vehicle_id"])
            if vehicle.exists():
                if not vals.get("source_location_id") and hasattr(vehicle, "stock_location_id") and vehicle.stock_location_id:
                    vals["source_location_id"] = vehicle.stock_location_id.id

        result = super().write(vals)
        self._sync_plan_line_state()
        return result

    def action_recompute_visit_health(self):
        self.ensure_one()
        self._compute_sale_order_count()
        self._compute_payment_totals()
        self._compute_refill_picking_count()
        self._compute_return_picking_count()
        self._compute_near_expiry_status()
        if hasattr(self, "_compute_visit_document_links"):
            self._compute_visit_document_links()
        if hasattr(self, "_compute_ux_workflow"):
            self._compute_ux_workflow()
        self._sync_plan_line_state()
        return self._phase0_notification(
            _("Visit Health Refreshed"),
            _("Visit workflow and financial indicators were refreshed successfully."),
        )

    def action_visit_diagnostics(self):
        self.ensure_one()
        checks = []
        if not self.company_id:
            checks.append(_("Missing company"))
        if not self.outlet_id:
            checks.append(_("Missing outlet"))
        if not self.vehicle_id:
            checks.append(_("Missing vehicle"))
        if not self.source_location_id:
            checks.append(_("Missing source location"))
        if not self.destination_location_id:
            checks.append(_("Missing destination location"))
        if self.has_pending_near_expiry:
            checks.append(_("Pending near expiry decisions: %s") % self.pending_near_expiry_line_count)
        draft_payments = self.payment_ids.filtered(lambda p: p.state == "draft")
        if draft_payments:
            checks.append(_("Draft payments: %s") % len(draft_payments))
        if self.refill_backorder_id:
            checks.append(_("Pending refill backorder exists"))
        if not checks:
            checks.append(_("No immediate diagnostics issues detected."))

        return self._phase0_notification(
            _("Visit Diagnostics"),
            " | ".join(checks),
            notif_type="warning" if len(checks) > 1 or checks[0] != _("No immediate diagnostics issues detected.") else "success",
            sticky=True,
        )

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
                "visit_process_state": "checked_in",
                "start_datetime": fields.Datetime.now(),
                "end_datetime": False,
                "no_sale_reason": False,
                "collection_skip_reason": False,
                "has_returns": False,
                "returns_step_done": False,
                "has_refill": False,
                "has_pending_refill": False,
                "no_refill": False,
                "source_location_id": rec.vehicle_id.stock_location_id.id if rec.vehicle_id and getattr(rec.vehicle_id, "stock_location_id", False) else False,
                "destination_location_id": rec.outlet_id.stock_location_id.id if rec.outlet_id and getattr(rec.outlet_id, "stock_location_id", False) else False,
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

    def _get_linked_route_sale_delivery(self):
        self.ensure_one()
        if not self.sale_order_id:
            return self.env["stock.picking"]

        domain = [
            ("route_visit_id", "=", self.id),
            ("origin", "=", self.sale_order_id.name),
            ("state", "!=", "cancel"),
        ]

        if self.outlet_id and getattr(self.outlet_id, "stock_location_id", False):
            domain.append(("location_id", "=", self.outlet_id.stock_location_id.id))

        return self.env["stock.picking"].search(domain, order="id desc", limit=1)

    def _get_route_sale_delivery_form_action(self, picking):
        self.ensure_one()
        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        action["res_id"] = picking.id
        action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]
        action["context"] = dict(self.env.context, default_route_visit_id=self.id)
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
            confirm_result = self.sale_order_id.action_confirm()
            if isinstance(confirm_result, dict):
                return confirm_result
            return self._get_sale_order_form_action(self.sale_order_id)

        sale_order = self.env["sale.order"].create(self._prepare_sale_order_vals())
        self.sale_order_id = sale_order.id
        confirm_result = sale_order.action_confirm()
        if isinstance(confirm_result, dict):
            return confirm_result

        return self._get_sale_order_form_action(sale_order)

    def action_view_sale_order(self):
        self.ensure_one()

        if not self.sale_order_id:
            raise UserError(_("There is no sale order linked to this visit."))

        return self._get_sale_order_form_action(self.sale_order_id)

    def action_view_pending_refill(self):
        self.ensure_one()

        if not self.refill_backorder_id:
            raise UserError(_("There is no pending refill for this visit."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Pending Refill"),
            "res_model": "route.refill.backorder",
            "view_mode": "form",
            "res_id": self.refill_backorder_id.id,
            "target": "current",
        }

    def action_ux_view_refill_transfer(self):
        self.ensure_one()

        if not self.refill_picking_id:
            raise UserError(_("There is no refill transfer for this visit."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Refill Transfer"),
            "res_model": "stock.picking",
            "view_mode": "form",
            "res_id": self.refill_picking_id.id,
            "target": "current",
        }

    def action_end_visit(self):
        self.ensure_one()

        if self.state != "in_progress":
            raise UserError(_("Only visits in progress can be ended."))

        self._raise_pending_near_expiry_error()

        if self.sale_order_id and self.sale_order_id.state in ("draft", "sent"):
            raise UserError(
                _(
                    "The linked Sale Order is still not confirmed. "
                    "Please confirm it first or end the visit without sale using the wizard."
                )
            )

        if self.sale_order_id:
            delivery = self._get_linked_route_sale_delivery()
            if delivery and delivery.state != "done":
                return self._get_route_sale_delivery_form_action(delivery)

            if not delivery:
                return self._get_sale_order_form_action(self.sale_order_id)

            self.with_context(route_visit_force_write=True).write({
                "state": "done",
                "visit_process_state": "done",
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
            rec.with_context(route_visit_force_write=True).write({
                "state": "cancel",
                "visit_process_state": "cancel",
            })

    def action_reset_to_draft(self):
        for rec in self:
            rec.with_context(route_visit_force_write=True).write({
                "state": "draft",
                "visit_process_state": "draft",
                "start_datetime": False,
                "end_datetime": False,
                "sale_order_id": False,
                "no_sale_reason": False,
                "collection_skip_reason": False,
                "has_returns": False,
                "returns_step_done": False,
                "has_refill": False,
                "has_pending_refill": False,
                "no_refill": False,
                "refill_datetime": False,
                "refill_backorder_id": False,
                "refill_picking_id": False,
                "source_location_id": False,
                "destination_location_id": False,
            })
