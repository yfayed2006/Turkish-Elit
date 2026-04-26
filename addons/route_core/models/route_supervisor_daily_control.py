from datetime import datetime, time, timedelta

from odoo import _, api, fields, models


class RouteSupervisorDailyControl(models.TransientModel):
    _name = "route.supervisor.daily.control"
    _description = "Supervisor Daily Control Dashboard"
    _rec_name = "name"

    name = fields.Char(
        string="Name",
        default=lambda self: _("Supervisor Daily Control"),
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        readonly=True,
    )
    control_date = fields.Date(
        string="Visit Date",
        required=True,
        default=fields.Date.context_today,
    )
    salesperson_id = fields.Many2one(
        "res.users",
        string="Salesperson",
    )
    vehicle_id = fields.Many2one(
        "route.vehicle",
        string="Vehicle",
    )
    area_id = fields.Many2one(
        "route.area",
        string="Area",
    )
    outlet_id = fields.Many2one(
        "route.outlet",
        string="Outlet",
    )
    visit_status_filter = fields.Selection(
        [
            ("all", "All Visits"),
            ("not_started", "Not Started"),
            ("active", "Active / In Progress"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        string="Visit Status",
        default="all",
        required=True,
    )
    location_status_filter = fields.Selection(
        [
            ("all", "All Location Statuses"),
            ("attention", "Location Attention"),
            ("pending_checkin", "No Location Check-in"),
            ("outlet_missing", "No Outlet Location"),
            ("inside_zone", "Inside Zone"),
            ("outside_zone", "Outside Zone"),
            ("accepted", "Accepted"),
            ("needs_correction", "Needs Correction"),
        ],
        string="Location Status",
        default="all",
        required=True,
    )

    plan_count = fields.Integer(string="Daily Plans", compute="_compute_dashboard")
    finalized_plan_count = fields.Integer(string="Finalized Plans", compute="_compute_dashboard")
    not_finalized_plan_count = fields.Integer(string="Not Finalized", compute="_compute_dashboard")

    total_visit_count = fields.Integer(string="Today's Visits", compute="_compute_dashboard")
    filtered_visit_count = fields.Integer(string="Filtered Visits", compute="_compute_dashboard")
    not_started_count = fields.Integer(string="Not Started", compute="_compute_dashboard")
    active_visit_count = fields.Integer(string="Active", compute="_compute_dashboard")
    done_visit_count = fields.Integer(string="Done", compute="_compute_dashboard")
    cancelled_visit_count = fields.Integer(string="Cancelled", compute="_compute_dashboard")

    no_checkin_count = fields.Integer(string="No Check-in", compute="_compute_dashboard")
    no_outlet_location_count = fields.Integer(string="No Outlet Location", compute="_compute_dashboard")
    outside_zone_count = fields.Integer(string="Outside Zone", compute="_compute_dashboard")
    needs_location_review_count = fields.Integer(string="Needs Location Review", compute="_compute_dashboard")
    location_accepted_count = fields.Integer(string="Location Accepted", compute="_compute_dashboard")
    location_correction_count = fields.Integer(string="Needs Correction", compute="_compute_dashboard")

    net_due_amount = fields.Monetary(
        string="Total Due",
        currency_field="currency_id",
        compute="_compute_dashboard",
    )
    collected_amount = fields.Monetary(
        string="Collected",
        currency_field="currency_id",
        compute="_compute_dashboard",
    )
    remaining_due_amount = fields.Monetary(
        string="Open Due",
        currency_field="currency_id",
        compute="_compute_dashboard",
    )
    promise_amount = fields.Monetary(
        string="Open Promise Amount",
        currency_field="currency_id",
        compute="_compute_dashboard",
    )
    confirmed_payment_count = fields.Integer(string="Confirmed Collections", compute="_compute_dashboard")
    open_promise_count = fields.Integer(string="Open Promises", compute="_compute_dashboard")

    daily_visit_ids = fields.Many2many(
        "route.visit",
        string="Daily Visit Cards",
        compute="_compute_dashboard",
        readonly=True,
    )
    daily_plan_ids = fields.Many2many(
        "route.plan",
        string="Daily Plans",
        compute="_compute_dashboard",
        readonly=True,
    )
    daily_payment_ids = fields.Many2many(
        "route.visit.payment",
        string="Daily Collections",
        compute="_compute_dashboard",
        readonly=True,
    )

    def _get_base_visit_domain(self, include_status_filter=True, include_location_filter=True):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id or self.env.company.id),
            ("date", "=", self.control_date or fields.Date.context_today(self)),
        ]
        if self.salesperson_id:
            domain.append(("user_id", "=", self.salesperson_id.id))
        if self.vehicle_id:
            domain.append(("vehicle_id", "=", self.vehicle_id.id))
        if self.area_id:
            domain.append(("area_id", "=", self.area_id.id))
        if self.outlet_id:
            domain.append(("outlet_id", "=", self.outlet_id.id))
        if include_status_filter:
            domain += self._get_visit_status_domain()
        if include_location_filter:
            domain += self._get_location_status_domain()
        return domain

    def _get_visit_status_domain(self):
        self.ensure_one()
        if self.visit_status_filter == "not_started":
            return [("visit_process_state", "=", "draft")]
        if self.visit_status_filter == "active":
            return [("visit_process_state", "not in", ["draft", "done", "cancel"])]
        if self.visit_status_filter == "done":
            return [("visit_process_state", "=", "done")]
        if self.visit_status_filter == "cancel":
            return [("visit_process_state", "=", "cancel")]
        return []

    def _get_location_status_domain(self):
        self.ensure_one()
        if self.location_status_filter == "attention":
            return [
                "|",
                "|",
                ("geo_review_state", "in", ["pending_checkin", "outlet_missing", "outside_no_reason", "outside_with_reason"]),
                ("geo_review_required", "=", True),
                ("geo_review_supervisor_decision", "=", "needs_correction"),
            ]
        if self.location_status_filter == "pending_checkin":
            return [("geo_review_state", "=", "pending_checkin")]
        if self.location_status_filter == "outlet_missing":
            return [("geo_review_state", "=", "outlet_missing")]
        if self.location_status_filter == "inside_zone":
            return [("geo_review_state", "=", "inside_zone")]
        if self.location_status_filter == "outside_zone":
            return [("geo_review_state", "in", ["outside_no_reason", "outside_with_reason"])]
        if self.location_status_filter == "accepted":
            return [("geo_review_supervisor_decision", "=", "accepted")]
        if self.location_status_filter == "needs_correction":
            return [("geo_review_supervisor_decision", "=", "needs_correction")]
        return []

    def _get_plan_domain(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id or self.env.company.id),
            ("date", "=", self.control_date or fields.Date.context_today(self)),
        ]
        if self.salesperson_id:
            domain.append(("user_id", "=", self.salesperson_id.id))
        if self.vehicle_id:
            domain.append(("vehicle_id", "=", self.vehicle_id.id))
        if self.area_id:
            domain.append(("area_id", "=", self.area_id.id))
        return domain

    def _get_payment_domain(self):
        self.ensure_one()
        target_date = self.control_date or fields.Date.context_today(self)
        start_dt = datetime.combine(target_date, time.min)
        end_dt = start_dt + timedelta(days=1)
        domain = [
            ("company_id", "=", self.company_id.id or self.env.company.id),
            ("state", "=", "confirmed"),
            ("payment_date", ">=", fields.Datetime.to_string(start_dt)),
            ("payment_date", "<", fields.Datetime.to_string(end_dt)),
        ]
        if self.salesperson_id:
            domain.append(("salesperson_id", "=", self.salesperson_id.id))
        if self.area_id:
            domain.append(("area_id", "=", self.area_id.id))
        if self.outlet_id:
            domain.append(("outlet_id", "=", self.outlet_id.id))
        return domain

    @api.depends(
        "company_id",
        "control_date",
        "salesperson_id",
        "vehicle_id",
        "area_id",
        "outlet_id",
        "visit_status_filter",
        "location_status_filter",
    )
    def _compute_dashboard(self):
        Visit = self.env["route.visit"]
        Plan = self.env["route.plan"]
        Payment = self.env["route.visit.payment"]
        for dashboard in self:
            counter_visits = Visit.search(
                dashboard._get_base_visit_domain(include_status_filter=False, include_location_filter=False)
            )
            filtered_visits = Visit.search(
                dashboard._get_base_visit_domain(include_status_filter=True, include_location_filter=True),
                order="date desc, start_datetime desc, id desc",
            )
            plans = Plan.search(dashboard._get_plan_domain(), order="date desc, id desc")
            payments = Payment.search(dashboard._get_payment_domain(), order="payment_date desc, id desc")
            if dashboard.vehicle_id:
                payments = payments.filtered(
                    lambda payment: (payment.visit_id and payment.visit_id.vehicle_id == dashboard.vehicle_id)
                    or (payment.settlement_visit_id and payment.settlement_visit_id.vehicle_id == dashboard.vehicle_id)
                )

            promise_payments = Payment.search([
                ("company_id", "=", dashboard.company_id.id or dashboard.env.company.id),
                ("state", "!=", "cancelled"),
                ("promise_amount", ">", 0),
            ])
            if dashboard.salesperson_id:
                promise_payments = promise_payments.filtered(lambda payment: payment.salesperson_id == dashboard.salesperson_id)
            if dashboard.vehicle_id:
                promise_payments = promise_payments.filtered(
                    lambda payment: (payment.visit_id and payment.visit_id.vehicle_id == dashboard.vehicle_id)
                    or (payment.settlement_visit_id and payment.settlement_visit_id.vehicle_id == dashboard.vehicle_id)
                )
            if dashboard.area_id:
                promise_payments = promise_payments.filtered(lambda payment: payment.area_id == dashboard.area_id)
            if dashboard.outlet_id:
                promise_payments = promise_payments.filtered(lambda payment: payment.outlet_id == dashboard.outlet_id)
            open_promises = promise_payments.filtered(lambda payment: payment.promise_status in ("open", "due_today", "overdue"))

            dashboard.plan_count = len(plans)
            dashboard.finalized_plan_count = len(plans.filtered(lambda plan: plan.planning_finalized))
            dashboard.not_finalized_plan_count = len(plans.filtered(lambda plan: not plan.planning_finalized))

            dashboard.total_visit_count = len(counter_visits)
            dashboard.filtered_visit_count = len(filtered_visits)
            dashboard.not_started_count = len(counter_visits.filtered(lambda visit: visit.visit_process_state == "draft"))
            dashboard.active_visit_count = len(counter_visits.filtered(lambda visit: visit.visit_process_state not in ["draft", "done", "cancel"]))
            dashboard.done_visit_count = len(counter_visits.filtered(lambda visit: visit.visit_process_state == "done"))
            dashboard.cancelled_visit_count = len(counter_visits.filtered(lambda visit: visit.visit_process_state == "cancel"))

            dashboard.no_checkin_count = len(counter_visits.filtered(lambda visit: visit.geo_review_state == "pending_checkin"))
            dashboard.no_outlet_location_count = len(counter_visits.filtered(lambda visit: visit.geo_review_state == "outlet_missing"))
            dashboard.outside_zone_count = len(counter_visits.filtered(lambda visit: visit.geo_review_state in ["outside_no_reason", "outside_with_reason"]))
            dashboard.needs_location_review_count = len(counter_visits.filtered(lambda visit: visit.geo_review_required and not visit.geo_review_supervisor_decision))
            dashboard.location_accepted_count = len(counter_visits.filtered(lambda visit: visit.geo_review_supervisor_decision == "accepted"))
            dashboard.location_correction_count = len(counter_visits.filtered(lambda visit: visit.geo_review_supervisor_decision == "needs_correction"))

            dashboard.net_due_amount = sum(counter_visits.mapped("net_due_amount")) if counter_visits else 0.0
            dashboard.collected_amount = sum(counter_visits.mapped("collected_amount")) if counter_visits else 0.0
            dashboard.remaining_due_amount = sum(counter_visits.mapped("remaining_due_amount")) if counter_visits else 0.0
            dashboard.promise_amount = sum(open_promises.mapped("promise_amount")) if open_promises else 0.0
            dashboard.confirmed_payment_count = len(payments)
            dashboard.open_promise_count = len(open_promises)

            dashboard.daily_visit_ids = [(6, 0, filtered_visits.ids)]
            dashboard.daily_plan_ids = [(6, 0, plans.ids)]
            dashboard.daily_payment_ids = [(6, 0, payments.ids)]

    @api.model
    def action_open_daily_control_dashboard(self):
        dashboard = self.create(
            {
                "name": _("Supervisor Daily Control"),
                "company_id": self.env.company.id,
                "control_date": fields.Date.context_today(self),
                "visit_status_filter": "all",
                "location_status_filter": "all",
            }
        )
        view = self.env.ref("route_core.view_route_supervisor_daily_control_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Supervisor Daily Control"),
            "res_model": "route.supervisor.daily.control",
            "res_id": dashboard.id,
            "view_mode": "form",
            "target": "current",
            "context": {"create": False, "edit": True, "delete": False},
        }
        if view:
            action["views"] = [(view.id, "form")]
        return action

    def action_refresh_dashboard(self):
        return {"type": "ir.actions.client", "tag": "reload"}

    def _action_open_visits(self, name, domain):
        self.ensure_one()
        views = []
        kanban_view = self.env.ref("route_core.view_route_supervisor_daily_visit_kanban", raise_if_not_found=False)
        list_view = self.env.ref("route_core.view_route_visit_tree", raise_if_not_found=False)
        form_view = self.env.ref("route_core.view_route_visit_form", raise_if_not_found=False)
        if kanban_view:
            views.append((kanban_view.id, "kanban"))
        if list_view:
            views.append((list_view.id, "list"))
        if form_view:
            views.append((form_view.id, "form"))
        action = {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": "route.visit",
            "view_mode": "kanban,list,form",
            "domain": domain,
            "context": {"create": False, "edit": True, "delete": False},
        }
        if views:
            action["views"] = views
        search_view = self.env.ref("route_core.view_route_supervisor_daily_visit_search", raise_if_not_found=False)
        if search_view:
            action["search_view_id"] = search_view.id
        return action

    def action_open_filtered_visits(self):
        return self._action_open_visits(_("Filtered Daily Visits"), self._get_base_visit_domain())

    def action_open_total_visits(self):
        return self._action_open_visits(
            _("Today's Visits"),
            self._get_base_visit_domain(include_status_filter=False, include_location_filter=False),
        )

    def action_open_not_started_visits(self):
        return self._action_open_visits(
            _("Not Started Visits"),
            self._get_base_visit_domain(include_status_filter=False, include_location_filter=False)
            + [("visit_process_state", "=", "draft")],
        )

    def action_open_active_visits(self):
        return self._action_open_visits(
            _("Active Visits"),
            self._get_base_visit_domain(include_status_filter=False, include_location_filter=False)
            + [("visit_process_state", "not in", ["draft", "done", "cancel"])],
        )

    def action_open_done_visits(self):
        return self._action_open_visits(
            _("Done Visits"),
            self._get_base_visit_domain(include_status_filter=False, include_location_filter=False)
            + [("visit_process_state", "=", "done")],
        )

    def action_open_location_attention_visits(self):
        return self._action_open_visits(
            _("Visits Requiring Location Attention"),
            self._get_base_visit_domain(include_status_filter=False, include_location_filter=False)
            + [
                "|",
                "|",
                ("geo_review_state", "in", ["pending_checkin", "outlet_missing", "outside_no_reason", "outside_with_reason"]),
                ("geo_review_required", "=", True),
                ("geo_review_supervisor_decision", "=", "needs_correction"),
            ],
        )

    def action_open_open_due_visits(self):
        visits = self.env["route.visit"].search(
            self._get_base_visit_domain(include_status_filter=False, include_location_filter=False)
        ).filtered(lambda visit: (visit.remaining_due_amount or 0.0) > 0.0)
        return self._action_open_visits(_("Visits With Open Due"), [("id", "in", visits.ids)])

    def action_open_daily_plans(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Daily Route Plans"),
            "res_model": "route.plan",
            "view_mode": "list,form",
            "domain": self._get_plan_domain(),
            "context": {"create": False, "edit": True, "delete": False},
        }

    def action_open_daily_collections(self):
        self.ensure_one()
        views = []
        kanban_view = self.env.ref("route_core.view_route_visit_collection_kanban", raise_if_not_found=False)
        list_view = self.env.ref("route_core.view_route_visit_payment_list", raise_if_not_found=False)
        form_view = self.env.ref("route_core.view_route_visit_payment_form", raise_if_not_found=False)
        if kanban_view:
            views.append((kanban_view.id, "kanban"))
        if list_view:
            views.append((list_view.id, "list"))
        if form_view:
            views.append((form_view.id, "form"))
        action = {
            "type": "ir.actions.act_window",
            "name": _("Daily Collections"),
            "res_model": "route.visit.payment",
            "view_mode": "kanban,list,form",
            "domain": self._get_payment_domain(),
            "context": {"create": False, "edit": True, "delete": False},
        }
        if views:
            action["views"] = views
        return action

    def action_open_visit_location_control(self):
        self.ensure_one()
        values = {
            "name": _("Visit Location Control"),
            "company_id": self.company_id.id,
            "visit_date": self.control_date,
            "visit_process_filter": self.visit_status_filter,
            "geo_review_filter": "all",
        }
        if self.salesperson_id:
            values["salesperson_id"] = self.salesperson_id.id
        if self.vehicle_id:
            values["vehicle_id"] = self.vehicle_id.id
        if self.area_id:
            values["area_id"] = self.area_id.id
        if self.outlet_id:
            values["outlet_id"] = self.outlet_id.id
        center = self.env["route.geo.control.center"].create(values)
        view = self.env.ref("route_core.view_route_geo_control_center_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Visit Location Control"),
            "res_model": "route.geo.control.center",
            "res_id": center.id,
            "view_mode": "form",
            "target": "current",
            "context": {"create": False, "edit": True, "delete": False},
        }
        if view:
            action["views"] = [(view.id, "form")]
        return action
