from datetime import datetime, time, timedelta

from odoo import _, api, fields, models


class RouteSupervisorDailyClosing(models.TransientModel):
    _name = "route.supervisor.daily.closing"
    _description = "Supervisor Daily Closing Control"
    _rec_name = "name"

    name = fields.Char(
        string="Name",
        default=lambda self: _("Supervisor Daily Closing"),
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
    closing_date = fields.Date(
        string="Closing Date",
        required=True,
        default=fields.Date.context_today,
    )
    salesperson_id = fields.Many2one("res.users", string="Salesperson")
    vehicle_id = fields.Many2one("route.vehicle", string="Vehicle")
    city_id = fields.Many2one("route.city", string="City")
    area_id = fields.Many2one("route.area", string="Area")
    outlet_id = fields.Many2one("route.outlet", string="Outlet")

    total_plan_count = fields.Integer(string="Daily Plans", compute="_compute_closing_dashboard")
    finalized_plan_count = fields.Integer(string="Finalized Plans", compute="_compute_closing_dashboard")
    not_finalized_plan_count = fields.Integer(string="Not Finalized Plans", compute="_compute_closing_dashboard")

    total_visit_count = fields.Integer(string="Visits", compute="_compute_closing_dashboard")
    done_visit_count = fields.Integer(string="Done Visits", compute="_compute_closing_dashboard")
    unfinished_visit_count = fields.Integer(string="Unfinished Visits", compute="_compute_closing_dashboard")
    not_started_visit_count = fields.Integer(string="Not Started", compute="_compute_closing_dashboard")
    active_visit_count = fields.Integer(string="Active", compute="_compute_closing_dashboard")

    location_issue_count = fields.Integer(string="Location Issues", compute="_compute_closing_dashboard")
    open_due_visit_count = fields.Integer(string="Open Due Visits", compute="_compute_closing_dashboard")
    open_due_amount = fields.Monetary(string="Open Due", currency_field="currency_id", compute="_compute_closing_dashboard")
    open_promise_count = fields.Integer(string="Open Promises", compute="_compute_closing_dashboard")
    open_promise_amount = fields.Monetary(string="Promise Amount", currency_field="currency_id", compute="_compute_closing_dashboard")

    vehicle_closing_count = fields.Integer(string="Vehicle Closings", compute="_compute_closing_dashboard")
    vehicle_closing_closed_count = fields.Integer(string="Closed Vehicles", compute="_compute_closing_dashboard")
    vehicle_closing_pending_count = fields.Integer(string="Pending Vehicle Closings", compute="_compute_closing_dashboard")
    vehicle_closing_missing_count = fields.Integer(string="Missing Vehicle Closings", compute="_compute_closing_dashboard")

    loading_proposal_count = fields.Integer(string="Loading Proposals", compute="_compute_closing_dashboard")
    loading_pending_count = fields.Integer(string="Loading Pending", compute="_compute_closing_dashboard")
    pending_transfer_count = fields.Integer(string="Pending Transfers", compute="_compute_closing_dashboard")
    return_transfer_count = fields.Integer(string="Return Transfers", compute="_compute_closing_dashboard")
    refill_transfer_count = fields.Integer(string="Refill Transfers", compute="_compute_closing_dashboard")

    blocker_count = fields.Integer(string="Closing Blockers", compute="_compute_closing_dashboard")
    ready_to_close = fields.Boolean(string="Ready to Close", compute="_compute_closing_dashboard")
    readiness_label = fields.Char(string="Readiness", compute="_compute_closing_dashboard")
    readiness_note = fields.Char(string="Readiness Note", compute="_compute_closing_dashboard")

    daily_visit_ids = fields.Many2many(
        "route.visit",
        string="Daily Visits",
        compute="_compute_closing_dashboard",
        readonly=True,
    )
    daily_plan_ids = fields.Many2many(
        "route.plan",
        string="Daily Plans",
        compute="_compute_closing_dashboard",
        readonly=True,
    )
    vehicle_closing_ids = fields.Many2many(
        "route.vehicle.closing",
        string="Vehicle Closings",
        compute="_compute_closing_dashboard",
        readonly=True,
    )
    loading_proposal_ids = fields.Many2many(
        "route.loading.proposal",
        string="Loading Proposals",
        compute="_compute_closing_dashboard",
        readonly=True,
    )
    open_promise_payment_ids = fields.Many2many(
        "route.visit.payment",
        string="Open Promises",
        compute="_compute_closing_dashboard",
        readonly=True,
    )
    pending_transfer_ids = fields.Many2many(
        "stock.picking",
        string="Pending Transfers",
        compute="_compute_closing_dashboard",
        readonly=True,
    )
    issue_line_ids = fields.One2many(
        "route.supervisor.daily.closing.issue",
        "dashboard_id",
        string="Closing Checks",
        readonly=True,
    )

    @api.onchange("city_id")
    def _onchange_city_id(self):
        for rec in self:
            if rec.area_id and rec.area_id.city_id != rec.city_id:
                rec.area_id = False
            if rec.outlet_id and rec.outlet_id.route_city_id != rec.city_id:
                rec.outlet_id = False

    @api.onchange("area_id")
    def _onchange_area_id(self):
        for rec in self:
            if rec.area_id and not rec.city_id:
                rec.city_id = rec.area_id.city_id
            if rec.outlet_id and rec.outlet_id.area_id != rec.area_id:
                rec.outlet_id = False

    @api.onchange("outlet_id")
    def _onchange_outlet_id(self):
        for rec in self:
            if rec.outlet_id:
                rec.area_id = rec.outlet_id.area_id
                if rec.outlet_id.route_city_id:
                    rec.city_id = rec.outlet_id.route_city_id

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._rebuild_issue_lines()
        return records

    def write(self, vals):
        result = super().write(vals)
        watched_fields = {
            "company_id",
            "closing_date",
            "salesperson_id",
            "vehicle_id",
            "city_id",
            "area_id",
            "outlet_id",
        }
        if not self.env.context.get("skip_daily_closing_issue_rebuild") and watched_fields.intersection(vals):
            self._rebuild_issue_lines()
        return result

    @api.onchange("company_id", "closing_date", "salesperson_id", "vehicle_id", "city_id", "area_id", "outlet_id")
    def _onchange_rebuild_issue_lines(self):
        for dashboard in self:
            try:
                issue_values = dashboard._prepare_issue_line_values()
                dashboard.issue_line_ids = [(5, 0, 0)] + [(0, 0, vals) for vals in issue_values]
            except Exception:
                dashboard.issue_line_ids = [(5, 0, 0)]

    def _reset_computed_values(self):
        for rec in self:
            rec.total_plan_count = 0
            rec.finalized_plan_count = 0
            rec.not_finalized_plan_count = 0
            rec.total_visit_count = 0
            rec.done_visit_count = 0
            rec.unfinished_visit_count = 0
            rec.not_started_visit_count = 0
            rec.active_visit_count = 0
            rec.location_issue_count = 0
            rec.open_due_visit_count = 0
            rec.open_due_amount = 0.0
            rec.open_promise_count = 0
            rec.open_promise_amount = 0.0
            rec.vehicle_closing_count = 0
            rec.vehicle_closing_closed_count = 0
            rec.vehicle_closing_pending_count = 0
            rec.vehicle_closing_missing_count = 0
            rec.loading_proposal_count = 0
            rec.loading_pending_count = 0
            rec.pending_transfer_count = 0
            rec.return_transfer_count = 0
            rec.refill_transfer_count = 0
            rec.blocker_count = 0
            rec.ready_to_close = False
            rec.readiness_label = _("Not Ready")
            rec.readiness_note = _("Review the closing checks below.")
            rec.daily_visit_ids = [fields.Command.clear()]
            rec.daily_plan_ids = [fields.Command.clear()]
            rec.vehicle_closing_ids = [fields.Command.clear()]
            rec.loading_proposal_ids = [fields.Command.clear()]
            rec.open_promise_payment_ids = [fields.Command.clear()]
            rec.pending_transfer_ids = [fields.Command.clear()]

    def _base_visit_domain(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id or self.env.company.id),
            ("date", "=", self.closing_date or fields.Date.context_today(self)),
        ]
        if self.salesperson_id:
            domain.append(("user_id", "=", self.salesperson_id.id))
        if self.vehicle_id:
            domain.append(("vehicle_id", "=", self.vehicle_id.id))
        if self.city_id:
            domain += [
                "|",
                ("area_id.city_id", "=", self.city_id.id),
                ("outlet_id.route_city_id", "=", self.city_id.id),
            ]
        if self.area_id:
            domain.append(("area_id", "=", self.area_id.id))
        if self.outlet_id:
            domain.append(("outlet_id", "=", self.outlet_id.id))
        return domain

    def _plan_domain(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id or self.env.company.id),
            ("date", "=", self.closing_date or fields.Date.context_today(self)),
        ]
        if self.salesperson_id:
            domain.append(("user_id", "=", self.salesperson_id.id))
        if self.vehicle_id:
            domain.append(("vehicle_id", "=", self.vehicle_id.id))
        if self.city_id:
            domain += [
                "|",
                ("area_id.city_id", "=", self.city_id.id),
                ("search_area_ids.city_id", "=", self.city_id.id),
            ]
        if self.area_id:
            domain.append(("area_id", "=", self.area_id.id))
        return domain

    def _vehicle_closing_domain(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id or self.env.company.id),
            ("plan_date", "=", self.closing_date or fields.Date.context_today(self)),
        ]
        if self.salesperson_id:
            domain.append(("user_id", "=", self.salesperson_id.id))
        if self.vehicle_id:
            domain.append(("vehicle_id", "=", self.vehicle_id.id))
        return domain

    def _loading_domain(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id or self.env.company.id),
            ("plan_date", "=", self.closing_date or fields.Date.context_today(self)),
        ]
        if self.salesperson_id:
            domain.append(("user_id", "=", self.salesperson_id.id))
        if self.vehicle_id:
            domain.append(("vehicle_id", "=", self.vehicle_id.id))
        return domain

    def _promise_domain_stored(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id or self.env.company.id),
            ("promise_amount", ">", 0.0),
        ]
        if self.salesperson_id:
            domain.append(("salesperson_id", "=", self.salesperson_id.id))
        if self.area_id:
            domain.append(("area_id", "=", self.area_id.id))
        if self.outlet_id:
            domain.append(("outlet_id", "=", self.outlet_id.id))
        return domain

    def _filter_recordsets_for_city_area_outlet(self, visits, plans, payments, closings, proposals):
        self.ensure_one()
        if self.city_id:
            visits = visits.filtered(
                lambda visit: (visit.area_id and visit.area_id.city_id == self.city_id)
                or (visit.outlet_id and visit.outlet_id.route_city_id == self.city_id)
            )
            plans = plans.filtered(
                lambda plan: (plan.area_id and plan.area_id.city_id == self.city_id)
                or bool(plan.search_area_ids.filtered(lambda area: area.city_id == self.city_id))
            )
            payments = payments.filtered(
                lambda payment: (payment.area_id and payment.area_id.city_id == self.city_id)
                or (payment.outlet_id and payment.outlet_id.route_city_id == self.city_id)
            )
            closings = closings.filtered(
                lambda closing: closing.plan_id
                and ((closing.plan_id.area_id and closing.plan_id.area_id.city_id == self.city_id)
                     or bool(closing.plan_id.search_area_ids.filtered(lambda area: area.city_id == self.city_id)))
            )
            proposals = proposals.filtered(
                lambda proposal: proposal.plan_id
                and ((proposal.plan_id.area_id and proposal.plan_id.area_id.city_id == self.city_id)
                     or bool(proposal.plan_id.search_area_ids.filtered(lambda area: area.city_id == self.city_id)))
            )
        if self.area_id:
            visits = visits.filtered(lambda visit: visit.area_id == self.area_id)
            plans = plans.filtered(lambda plan: plan.area_id == self.area_id or self.area_id in plan.search_area_ids)
            payments = payments.filtered(lambda payment: payment.area_id == self.area_id)
            closings = closings.filtered(
                lambda closing: closing.plan_id and (closing.plan_id.area_id == self.area_id or self.area_id in closing.plan_id.search_area_ids)
            )
            proposals = proposals.filtered(
                lambda proposal: proposal.plan_id and (proposal.plan_id.area_id == self.area_id or self.area_id in proposal.plan_id.search_area_ids)
            )
        if self.outlet_id:
            payments = payments.filtered(lambda payment: payment.outlet_id == self.outlet_id)
        return visits, plans, payments, closings, proposals

    def _collect_dashboard_data(self):
        self.ensure_one()
        Visit = self.env["route.visit"]
        Plan = self.env["route.plan"]
        Payment = self.env["route.visit.payment"]
        Closing = self.env["route.vehicle.closing"]
        Proposal = self.env["route.loading.proposal"]
        Picking = self.env["stock.picking"]

        visits = Visit.search(self._base_visit_domain(), order="date desc, start_datetime desc, id desc")
        plans = Plan.search(self._plan_domain(), order="date desc, id desc")
        closings = Closing.search(self._vehicle_closing_domain(), order="plan_date desc, id desc")
        proposals = Proposal.search(self._loading_domain(), order="plan_date desc, id desc")
        payments = Payment.search(self._promise_domain_stored(), order="promise_date asc, id desc")

        if self.vehicle_id:
            payments = payments.filtered(
                lambda payment: (payment.visit_id and payment.visit_id.vehicle_id == self.vehicle_id)
                or (payment.settlement_visit_id and payment.settlement_visit_id.vehicle_id == self.vehicle_id)
            )
        visits, plans, payments, closings, proposals = self._filter_recordsets_for_city_area_outlet(visits, plans, payments, closings, proposals)
        open_promises = payments.filtered(lambda payment: payment.promise_status in ("open", "due_today", "overdue"))

        related_picking_ids = set()
        for visit in visits:
            if visit.refill_picking_id:
                related_picking_ids.add(visit.refill_picking_id.id)
            for picking in visit.return_picking_ids:
                related_picking_ids.add(picking.id)
        for proposal in proposals:
            if proposal.picking_id:
                related_picking_ids.add(proposal.picking_id.id)
        for closing in closings:
            for picking in closing.reconciliation_picking_ids:
                related_picking_ids.add(picking.id)
        pending_transfers = Picking.search([
            ("id", "in", list(related_picking_ids) or [0]),
            ("state", "not in", ["done", "cancel"]),
        ])
        return visits, plans, closings, proposals, open_promises, pending_transfers

    @api.depends("company_id", "closing_date", "salesperson_id", "vehicle_id", "city_id", "area_id", "outlet_id")
    def _compute_closing_dashboard(self):
        for dashboard in self:
            dashboard._reset_computed_values()
            try:
                visits, plans, closings, proposals, open_promises, pending_transfers = dashboard._collect_dashboard_data()
                done_visits = visits.filtered(lambda visit: visit.visit_process_state == "done")
                not_started_visits = visits.filtered(lambda visit: visit.visit_process_state == "draft")
                active_visits = visits.filtered(lambda visit: visit.visit_process_state not in ["draft", "done", "cancel"])
                unfinished_visits = visits.filtered(lambda visit: visit.visit_process_state not in ["done", "cancel"])
                location_issues = visits.filtered(
                    lambda visit: (visit.geo_review_required and not visit.geo_review_supervisor_decision)
                    or visit.geo_review_supervisor_decision == "needs_correction"
                    or visit.geo_review_state in ["pending_checkin", "outlet_missing"]
                )
                open_due_visits = visits.filtered(lambda visit: (visit.remaining_due_amount or 0.0) > 0.0)
                not_finalized_plans = plans.filtered(lambda plan: not plan.planning_finalized)
                closed_closings = closings.filtered(lambda closing: closing.state == "closed")
                pending_closings = closings.filtered(lambda closing: closing.state != "closed")
                missing_closings_count = len(plans.filtered(lambda plan: plan.vehicle_id and plan not in closings.mapped("plan_id")))
                pending_loading = proposals.filtered(
                    lambda proposal: proposal.state not in ["approved", "cancelled"]
                    or (proposal.picking_id and proposal.picking_id.state not in ["done", "cancel"])
                )
                return_pickings = visits.mapped("return_picking_ids").filtered(lambda picking: picking.state != "cancel")
                refill_pickings = visits.mapped("refill_picking_id").filtered(lambda picking: picking.state != "cancel")

                blocker_count = (
                    len(unfinished_visits)
                    + len(location_issues)
                    + len(open_due_visits)
                    + len(open_promises)
                    + len(not_finalized_plans)
                    + len(pending_closings)
                    + missing_closings_count
                    + len(pending_loading)
                    + len(pending_transfers)
                )

                dashboard.daily_visit_ids = [fields.Command.set(visits.ids)]
                dashboard.daily_plan_ids = [fields.Command.set(plans.ids)]
                dashboard.vehicle_closing_ids = [fields.Command.set(closings.ids)]
                dashboard.loading_proposal_ids = [fields.Command.set(proposals.ids)]
                dashboard.open_promise_payment_ids = [fields.Command.set(open_promises.ids)]
                dashboard.pending_transfer_ids = [fields.Command.set(pending_transfers.ids)]

                dashboard.total_plan_count = len(plans)
                dashboard.finalized_plan_count = len(plans.filtered("planning_finalized"))
                dashboard.not_finalized_plan_count = len(not_finalized_plans)
                dashboard.total_visit_count = len(visits)
                dashboard.done_visit_count = len(done_visits)
                dashboard.unfinished_visit_count = len(unfinished_visits)
                dashboard.not_started_visit_count = len(not_started_visits)
                dashboard.active_visit_count = len(active_visits)
                dashboard.location_issue_count = len(location_issues)
                dashboard.open_due_visit_count = len(open_due_visits)
                dashboard.open_due_amount = sum(open_due_visits.mapped("remaining_due_amount")) if open_due_visits else 0.0
                dashboard.open_promise_count = len(open_promises)
                dashboard.open_promise_amount = sum(open_promises.mapped("promise_amount")) if open_promises else 0.0
                dashboard.vehicle_closing_count = len(closings)
                dashboard.vehicle_closing_closed_count = len(closed_closings)
                dashboard.vehicle_closing_pending_count = len(pending_closings)
                dashboard.vehicle_closing_missing_count = missing_closings_count
                dashboard.loading_proposal_count = len(proposals)
                dashboard.loading_pending_count = len(pending_loading)
                dashboard.pending_transfer_count = len(pending_transfers)
                dashboard.return_transfer_count = len(return_pickings)
                dashboard.refill_transfer_count = len(refill_pickings)
                dashboard.blocker_count = blocker_count
                dashboard.ready_to_close = blocker_count == 0
                if dashboard.ready_to_close:
                    dashboard.readiness_label = _("Ready to Close")
                    dashboard.readiness_note = _("No blocking items were found for the selected date and filters.")
                else:
                    dashboard.readiness_label = _("Not Ready")
                    dashboard.readiness_note = _("Resolve the blocking items before closing the day.")
            except Exception:
                dashboard._reset_computed_values()

    def _prepare_issue_line_values(self):
        self.ensure_one()
        visits, plans, closings, proposals, open_promises, pending_transfers = self._collect_dashboard_data()
        lines = []

        def add(sequence, code, title, count, subtitle, severity="warning", amount=0.0, button_label="Open"):
            if not count and code != "ready":
                return
            lines.append({
                "sequence": sequence,
                "code": code,
                "title": title,
                "count": count,
                "subtitle": subtitle or "",
                "severity": severity,
                "amount": amount or 0.0,
                "button_label": button_label,
            })

        unfinished = visits.filtered(lambda visit: visit.visit_process_state not in ["done", "cancel"])
        not_started = visits.filtered(lambda visit: visit.visit_process_state == "draft")
        open_due = visits.filtered(lambda visit: (visit.remaining_due_amount or 0.0) > 0.0)
        location_issues = visits.filtered(
            lambda visit: (visit.geo_review_required and not visit.geo_review_supervisor_decision)
            or visit.geo_review_supervisor_decision == "needs_correction"
            or visit.geo_review_state in ["pending_checkin", "outlet_missing"]
        )
        not_finalized = plans.filtered(lambda plan: not plan.planning_finalized)
        pending_closings = closings.filtered(lambda closing: closing.state != "closed")
        missing_closings = plans.filtered(lambda plan: plan.vehicle_id and plan not in closings.mapped("plan_id"))
        pending_loading = proposals.filtered(
            lambda proposal: proposal.state not in ["approved", "cancelled"]
            or (proposal.picking_id and proposal.picking_id.state not in ["done", "cancel"])
        )

        add(10, "unfinished_visits", _("Unfinished Visits"), len(unfinished), _("Visits that are not done or cancelled."), "danger", button_label=_("Open Visits"))
        add(20, "not_started_visits", _("Not Started Visits"), len(not_started), _("Planned visits not started yet."), "warning", button_label=_("Open Visits"))
        add(30, "location_issues", _("Location Review Pending"), len(location_issues), _("Location issues need supervisor review."), "warning", button_label=_("Open Location"))
        add(40, "open_due", _("Open Due"), len(open_due), _("Visits with remaining due amount."), "danger", sum(open_due.mapped("remaining_due_amount")) if open_due else 0.0, button_label=_("Open Visits"))
        add(50, "open_promises", _("Open Promises"), len(open_promises), _("Open, due today, or overdue promises."), "warning", sum(open_promises.mapped("promise_amount")) if open_promises else 0.0, button_label=_("Open Promises"))
        add(60, "not_finalized_plans", _("Plans Not Finalized"), len(not_finalized), _("Daily route plans still need finalization."), "warning", button_label=_("Open Plans"))
        add(70, "vehicle_closing_pending", _("Vehicle Closing Pending"), len(pending_closings) + len(missing_closings), _("Vehicle closing is missing or still draft."), "danger", button_label=_("Open Closings"))
        add(80, "loading_pending", _("Loading / Transfer Pending"), len(pending_loading) + len(pending_transfers), _("Loading proposals or related transfers are not fully completed."), "warning", button_label=_("Open Loading"))
        if not lines:
            add(90, "ready", _("Ready to Close Day"), 0, _("No blocking items were found."), "success", button_label=_("Refresh"))
        return lines

    def _rebuild_issue_lines(self):
        for dashboard in self:
            try:
                issue_values = dashboard._prepare_issue_line_values()
                dashboard.with_context(skip_daily_closing_issue_rebuild=True).write({
                    "issue_line_ids": [(5, 0, 0)] + [(0, 0, vals) for vals in issue_values]
                })
            except Exception:
                dashboard.with_context(skip_daily_closing_issue_rebuild=True).write({"issue_line_ids": [(5, 0, 0)]})

    @api.model
    def action_open_daily_closing_dashboard(self):
        dashboard = self.create({
            "name": _("Supervisor Daily Closing"),
            "company_id": self.env.company.id,
            "closing_date": fields.Date.context_today(self),
        })
        view = self.env.ref("route_core.view_route_supervisor_daily_closing_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Supervisor Daily Closing"),
            "res_model": "route.supervisor.daily.closing",
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

    def action_open_daily_control(self):
        server_action = self.env.ref("route_core.server_action_open_route_supervisor_daily_control", raise_if_not_found=False)
        if server_action:
            return server_action.run()
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

    def action_open_all_visits(self):
        return self._action_open_visits(_("Daily Visits"), self._base_visit_domain())

    def action_open_unfinished_visits(self):
        return self._action_open_visits(
            _("Unfinished Visits"),
            self._base_visit_domain() + [("visit_process_state", "not in", ["done", "cancel"])],
        )

    def action_open_not_started_visits(self):
        return self._action_open_visits(
            _("Not Started Visits"),
            self._base_visit_domain() + [("visit_process_state", "=", "draft")],
        )

    def action_open_location_issues(self):
        return self._action_open_visits(
            _("Location Review Pending"),
            self._base_visit_domain()
            + [
                "|",
                "|",
                ("geo_review_state", "in", ["pending_checkin", "outlet_missing"]),
                ("geo_review_required", "=", True),
                ("geo_review_supervisor_decision", "=", "needs_correction"),
            ],
        )

    def action_open_open_due_visits(self):
        visits = self.env["route.visit"].search(self._base_visit_domain()).filtered(
            lambda visit: (visit.remaining_due_amount or 0.0) > 0.0
        )
        return self._action_open_visits(_("Visits With Open Due"), [("id", "in", visits.ids or [0])])

    def action_open_daily_plans(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_plan", raise_if_not_found=False)
        result = action.read()[0] if action else {
            "type": "ir.actions.act_window",
            "name": _("Daily Plans"),
            "res_model": "route.plan",
            "view_mode": "list,form",
        }
        result.update({
            "name": _("Daily Plans to Close"),
            "domain": [("id", "in", self.daily_plan_ids.ids or [0])],
            "context": {"create": False, "edit": True, "delete": False},
        })
        return result

    def action_open_vehicle_closings(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_vehicle_closing", raise_if_not_found=False)
        result = action.read()[0] if action else {
            "type": "ir.actions.act_window",
            "name": _("Vehicle Closings"),
            "res_model": "route.vehicle.closing",
            "view_mode": "list,form",
        }
        result.update({
            "name": _("Vehicle Closings to Review"),
            "domain": [("id", "in", self.vehicle_closing_ids.ids or [0])],
            "context": {"create": False, "edit": True, "delete": False},
        })
        return result

    def action_open_loading_proposals(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_loading_proposal", raise_if_not_found=False)
        result = action.read()[0] if action else {
            "type": "ir.actions.act_window",
            "name": _("Loading Proposals"),
            "res_model": "route.loading.proposal",
            "view_mode": "list,form",
        }
        result.update({
            "name": _("Loading Proposals to Review"),
            "domain": [("id", "in", self.loading_proposal_ids.ids or [0])],
            "context": {"create": False, "edit": True, "delete": False},
        })
        return result

    def action_open_pending_transfers(self):
        self.ensure_one()
        action = self.env.ref("stock.action_picking_tree_all", raise_if_not_found=False)
        result = action.read()[0] if action else {
            "type": "ir.actions.act_window",
            "name": _("Pending Transfers"),
            "res_model": "stock.picking",
            "view_mode": "list,form",
        }
        result.update({
            "name": _("Pending Transfers"),
            "domain": [("id", "in", self.pending_transfer_ids.ids or [0])],
            "context": {"create": False, "edit": True, "delete": False},
        })
        return result

    def action_open_promises(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_visit_payment", raise_if_not_found=False)
        result = action.read()[0] if action else {
            "type": "ir.actions.act_window",
            "name": _("Open Promises"),
            "res_model": "route.visit.payment",
            "view_mode": "kanban,list,form",
        }
        result.update({
            "name": _("Open Promises"),
            "domain": [("id", "in", self.open_promise_payment_ids.ids or [0])],
            "context": {"create": False, "edit": True, "delete": False},
        })
        return result


class RouteSupervisorDailyClosingIssue(models.TransientModel):
    _name = "route.supervisor.daily.closing.issue"
    _description = "Daily Closing Issue Card"
    _order = "sequence, id"

    dashboard_id = fields.Many2one(
        "route.supervisor.daily.closing",
        string="Dashboard",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    code = fields.Selection(
        [
            ("unfinished_visits", "Unfinished Visits"),
            ("not_started_visits", "Not Started Visits"),
            ("location_issues", "Location Issues"),
            ("open_due", "Open Due"),
            ("open_promises", "Open Promises"),
            ("not_finalized_plans", "Plans Not Finalized"),
            ("vehicle_closing_pending", "Vehicle Closing Pending"),
            ("loading_pending", "Loading Pending"),
            ("ready", "Ready"),
        ],
        string="Issue Type",
        required=True,
    )
    title = fields.Char(string="Title", required=True)
    subtitle = fields.Char(string="Description")
    count = fields.Integer(string="Count")
    amount = fields.Monetary(string="Amount", currency_field="currency_id")
    currency_id = fields.Many2one(related="dashboard_id.currency_id", readonly=True)
    severity = fields.Selection(
        [
            ("success", "Success"),
            ("info", "Info"),
            ("warning", "Warning"),
            ("danger", "Danger"),
        ],
        default="warning",
        required=True,
    )
    button_label = fields.Char(string="Button", default=lambda self: _("Open"))

    def action_open_issue_details(self):
        self.ensure_one()
        dashboard = self.dashboard_id
        if self.code == "unfinished_visits":
            return dashboard.action_open_unfinished_visits()
        if self.code == "not_started_visits":
            return dashboard.action_open_not_started_visits()
        if self.code == "location_issues":
            return dashboard.action_open_location_issues()
        if self.code == "open_due":
            return dashboard.action_open_open_due_visits()
        if self.code == "open_promises":
            return dashboard.action_open_promises()
        if self.code == "not_finalized_plans":
            return dashboard.action_open_daily_plans()
        if self.code == "vehicle_closing_pending":
            return dashboard.action_open_vehicle_closings()
        if self.code == "loading_pending":
            return dashboard.action_open_loading_proposals()
        return dashboard.action_refresh_dashboard()
