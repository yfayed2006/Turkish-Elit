from odoo import _, api, fields, models


class RouteGeoControlCenter(models.TransientModel):
    _name = "route.geo.control.center"
    _description = "Route Geo Control Center"
    _rec_name = "name"

    name = fields.Char(
        string="Name",
        default=lambda self: _("Geo Control Center"),
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    visit_date = fields.Date(
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
    visit_process_filter = fields.Selection(
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
    geo_review_filter = fields.Selection(
        [
            ("all", "All Geo States"),
            ("pending_checkin", "Pending Check-in"),
            ("outlet_missing", "Outlet Location Missing"),
            ("inside_zone", "Inside Zone"),
            ("outside_zone", "Outside Zone"),
            ("outside_no_reason", "Outside - Missing Reason"),
            ("outside_with_reason", "Outside - Reason Recorded"),
            ("needs_review", "Needs Supervisor Review"),
            ("accepted", "Accepted by Supervisor"),
            ("needs_correction", "Needs Correction"),
        ],
        string="Geo State",
        default="all",
        required=True,
    )

    total_visit_count = fields.Integer(
        string="Today's Visits",
        compute="_compute_geo_dashboard",
    )
    not_started_count = fields.Integer(
        string="Not Started",
        compute="_compute_geo_dashboard",
    )
    active_visit_count = fields.Integer(
        string="Active",
        compute="_compute_geo_dashboard",
    )
    done_visit_count = fields.Integer(
        string="Done",
        compute="_compute_geo_dashboard",
    )
    pending_checkin_count = fields.Integer(
        string="Pending Check-in",
        compute="_compute_geo_dashboard",
    )
    outlet_missing_count = fields.Integer(
        string="Outlet Location Missing",
        compute="_compute_geo_dashboard",
    )
    inside_zone_count = fields.Integer(
        string="Inside Zone",
        compute="_compute_geo_dashboard",
    )
    outside_zone_count = fields.Integer(
        string="Outside Zone",
        compute="_compute_geo_dashboard",
    )
    outside_missing_reason_count = fields.Integer(
        string="Outside - Missing Reason",
        compute="_compute_geo_dashboard",
    )
    needs_review_count = fields.Integer(
        string="Needs Review",
        compute="_compute_geo_dashboard",
    )
    accepted_count = fields.Integer(
        string="Accepted",
        compute="_compute_geo_dashboard",
    )
    needs_correction_count = fields.Integer(
        string="Needs Correction",
        compute="_compute_geo_dashboard",
    )
    filtered_visit_count = fields.Integer(
        string="Filtered Visits",
        compute="_compute_geo_dashboard",
    )
    geo_visit_ids = fields.Many2many(
        "route.visit",
        string="Today Geo Visits",
        compute="_compute_geo_dashboard",
        readonly=True,
    )
    mapped_visit_count = fields.Integer(
        string="Mapped Visits",
        compute="_compute_geo_dashboard",
    )
    unmapped_visit_count = fields.Integer(
        string="No Map Point",
        compute="_compute_geo_dashboard",
    )
    live_map_html = fields.Html(
        string="Live Map",
        compute="_compute_live_map_html",
        sanitize=False,
        readonly=True,
    )
    live_map_note = fields.Char(
        string="Live Map Readiness",
        compute="_compute_geo_dashboard",
    )

    def _geo_live_map_url(self):
        self.ensure_one()
        return "/route_core/geo/live_map/frame/%s" % self.id

    @api.depends(
        "company_id",
        "visit_date",
        "salesperson_id",
        "vehicle_id",
        "area_id",
        "outlet_id",
        "visit_process_filter",
        "geo_review_filter",
    )
    def _compute_live_map_html(self):
        for center in self:
            if not center.id:
                center.live_map_html = _("Save the Geo Control Center before opening the live map.")
                continue
            center.live_map_html = (
                '<iframe src="%s" '
                'style="width:100%%; min-height:680px; height:calc(100vh - 230px); '
                'border:0; border-radius:12px; overflow:hidden;" '
                'loading="lazy" referrerpolicy="same-origin"></iframe>'
            ) % center._geo_live_map_url()

    def _get_base_visit_domain(self, include_process_filter=True):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id or self.env.company.id),
            ("date", "=", self.visit_date or fields.Date.context_today(self)),
        ]
        if self.salesperson_id:
            domain.append(("user_id", "=", self.salesperson_id.id))
        if self.vehicle_id:
            domain.append(("vehicle_id", "=", self.vehicle_id.id))
        if self.area_id:
            domain.append(("area_id", "=", self.area_id.id))
        if self.outlet_id:
            domain.append(("outlet_id", "=", self.outlet_id.id))
        if include_process_filter:
            domain += self._get_visit_process_domain()
        return domain

    def _get_visit_process_domain(self):
        self.ensure_one()
        if self.visit_process_filter == "not_started":
            return [("visit_process_state", "=", "draft")]
        if self.visit_process_filter == "active":
            return [("visit_process_state", "not in", ["draft", "done", "cancel"])]
        if self.visit_process_filter == "done":
            return [("visit_process_state", "=", "done")]
        if self.visit_process_filter == "cancel":
            return [("visit_process_state", "=", "cancel")]
        return []

    def _get_geo_review_domain(self):
        self.ensure_one()
        if self.geo_review_filter == "pending_checkin":
            return [("geo_review_state", "=", "pending_checkin")]
        if self.geo_review_filter == "outlet_missing":
            return [("geo_review_state", "=", "outlet_missing")]
        if self.geo_review_filter == "inside_zone":
            return [("geo_review_state", "=", "inside_zone")]
        if self.geo_review_filter == "outside_zone":
            return [("geo_review_state", "in", ["outside_no_reason", "outside_with_reason"])]
        if self.geo_review_filter == "outside_no_reason":
            return [("geo_review_state", "=", "outside_no_reason")]
        if self.geo_review_filter == "outside_with_reason":
            return [("geo_review_state", "=", "outside_with_reason")]
        if self.geo_review_filter == "needs_review":
            return [("geo_review_required", "=", True), ("geo_review_supervisor_decision", "=", False)]
        if self.geo_review_filter == "accepted":
            return [("geo_review_supervisor_decision", "=", "accepted")]
        if self.geo_review_filter == "needs_correction":
            return [("geo_review_supervisor_decision", "=", "needs_correction")]
        return []

    def _get_filtered_visit_domain(self):
        self.ensure_one()
        return self._get_base_visit_domain(include_process_filter=True) + self._get_geo_review_domain()

    @api.depends(
        "company_id",
        "visit_date",
        "salesperson_id",
        "vehicle_id",
        "area_id",
        "outlet_id",
        "visit_process_filter",
        "geo_review_filter",
    )
    def _compute_geo_dashboard(self):
        Visit = self.env["route.visit"]
        for center in self:
            counter_domain = center._get_base_visit_domain(include_process_filter=False)
            counter_visits = Visit.search(counter_domain)
            filtered_visits = Visit.search(
                center._get_filtered_visit_domain(),
                order="date desc, geo_checkin_datetime desc, id desc",
            )

            center.total_visit_count = len(counter_visits)
            center.not_started_count = len(counter_visits.filtered(lambda visit: visit.visit_process_state == "draft"))
            center.active_visit_count = len(counter_visits.filtered(lambda visit: visit.visit_process_state not in ["draft", "done", "cancel"]))
            center.done_visit_count = len(counter_visits.filtered(lambda visit: visit.visit_process_state == "done"))
            center.pending_checkin_count = len(counter_visits.filtered(lambda visit: visit.geo_review_state == "pending_checkin"))
            center.outlet_missing_count = len(counter_visits.filtered(lambda visit: visit.geo_review_state == "outlet_missing"))
            center.inside_zone_count = len(counter_visits.filtered(lambda visit: visit.geo_review_state == "inside_zone"))
            center.outside_zone_count = len(counter_visits.filtered(lambda visit: visit.geo_review_state in ["outside_no_reason", "outside_with_reason"]))
            center.outside_missing_reason_count = len(counter_visits.filtered(lambda visit: visit.geo_review_state == "outside_no_reason"))
            center.needs_review_count = len(counter_visits.filtered(lambda visit: visit.geo_review_required and not visit.geo_review_supervisor_decision))
            center.accepted_count = len(counter_visits.filtered(lambda visit: visit.geo_review_supervisor_decision == "accepted"))
            center.needs_correction_count = len(counter_visits.filtered(lambda visit: visit.geo_review_supervisor_decision == "needs_correction"))
            center.filtered_visit_count = len(filtered_visits)
            center.mapped_visit_count = len(filtered_visits.filtered(
                lambda visit: bool(
                    visit.geo_checkin_latitude
                    or visit.geo_checkin_longitude
                    or (visit.outlet_id and (visit.outlet_id.geo_latitude or visit.outlet_id.geo_longitude))
                )
            ))
            center.unmapped_visit_count = center.filtered_visit_count - center.mapped_visit_count
            center.geo_visit_ids = [(6, 0, filtered_visits.ids)]
            center.live_map_note = _("Ready for B6.2 Live Map.")

    @api.model
    def action_open_geo_control_center(self):
        center = self.create(
            {
                "name": _("Geo Control Center"),
                "company_id": self.env.company.id,
                "visit_date": fields.Date.context_today(self),
                "visit_process_filter": "all",
                "geo_review_filter": "all",
            }
        )
        view = self.env.ref("route_core.view_route_geo_control_center_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Geo Control Center"),
            "res_model": "route.geo.control.center",
            "res_id": center.id,
            "view_mode": "form",
            "target": "current",
            "context": {"create": False, "edit": True, "delete": False},
        }
        if view:
            action["views"] = [(view.id, "form")]
        return action

    def action_refresh_dashboard(self):
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_open_live_map(self):
        self.ensure_one()
        view = self.env.ref("route_core.view_route_geo_control_center_live_map_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Geo Live Map"),
            "res_model": "route.geo.control.center",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
            "context": {"create": False, "edit": True, "delete": False},
        }
        if view:
            action["views"] = [(view.id, "form")]
        return action

    def action_back_to_geo_dashboard(self):
        self.ensure_one()
        view = self.env.ref("route_core.view_route_geo_control_center_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Geo Control Center"),
            "res_model": "route.geo.control.center",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
            "context": {"create": False, "edit": True, "delete": False},
        }
        if view:
            action["views"] = [(view.id, "form")]
        return action

    def _action_open_geo_visits(self, name, domain):
        self.ensure_one()
        views = []
        kanban_view = self.env.ref("route_core.view_route_geo_control_visit_kanban", raise_if_not_found=False)
        list_view = self.env.ref("route_core.view_route_geo_review_list", raise_if_not_found=False)
        form_view = self.env.ref("route_core.view_route_geo_review_form", raise_if_not_found=False)
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
        search_view = self.env.ref("route_core.view_route_geo_control_card_search", raise_if_not_found=False)
        if search_view:
            action["search_view_id"] = search_view.id
        return action

    def _action_open_geo_review_list(self, name, domain):
        self.ensure_one()
        action_ref = self.env.ref("route_core.action_route_geo_review", raise_if_not_found=False)
        if action_ref:
            action = action_ref.read()[0]
            action.update(
                {
                    "name": name,
                    "domain": domain,
                    "view_mode": "list,form",
                    "context": {"create": False, "edit": True, "delete": False},
                }
            )
            return action
        views = []
        list_view = self.env.ref("route_core.view_route_geo_review_list", raise_if_not_found=False)
        form_view = self.env.ref("route_core.view_route_geo_review_form", raise_if_not_found=False)
        if list_view:
            views.append((list_view.id, "list"))
        if form_view:
            views.append((form_view.id, "form"))
        action = {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": "route.visit",
            "view_mode": "list,form",
            "domain": domain,
            "context": {"create": False, "edit": True, "delete": False},
        }
        if views:
            action["views"] = views
        search_view = self.env.ref("route_core.view_route_geo_review_search", raise_if_not_found=False)
        if search_view:
            action["search_view_id"] = search_view.id
        return action

    def action_open_filtered_visits(self):
        return self._action_open_geo_visits(_("Filtered Geo Visit Cards"), self._get_filtered_visit_domain())

    def action_open_total_visits(self):
        return self._action_open_geo_visits(_("Today's Geo Visits"), self._get_base_visit_domain(include_process_filter=False))

    def action_open_not_started_visits(self):
        return self._action_open_geo_visits(
            _("Not Started Visits"),
            self._get_base_visit_domain(include_process_filter=False) + [("visit_process_state", "=", "draft")],
        )

    def action_open_active_visits(self):
        return self._action_open_geo_visits(
            _("Active Geo Visits"),
            self._get_base_visit_domain(include_process_filter=False) + [("visit_process_state", "not in", ["draft", "done", "cancel"])],
        )

    def action_open_done_visits(self):
        return self._action_open_geo_visits(
            _("Done Geo Visits"),
            self._get_base_visit_domain(include_process_filter=False) + [("visit_process_state", "=", "done")],
        )

    def action_open_pending_checkin_visits(self):
        return self._action_open_geo_visits(
            _("Pending Geo Check-in"),
            self._get_base_visit_domain(include_process_filter=False) + [("geo_review_state", "=", "pending_checkin")],
        )

    def action_open_outlet_missing_visits(self):
        return self._action_open_geo_visits(
            _("Missing Outlet Location"),
            self._get_base_visit_domain(include_process_filter=False) + [("geo_review_state", "=", "outlet_missing")],
        )

    def action_open_inside_zone_visits(self):
        return self._action_open_geo_visits(
            _("Inside Zone Visits"),
            self._get_base_visit_domain(include_process_filter=False) + [("geo_review_state", "=", "inside_zone")],
        )

    def action_open_outside_zone_visits(self):
        return self._action_open_geo_visits(
            _("Outside Zone Visits"),
            self._get_base_visit_domain(include_process_filter=False) + [("geo_review_state", "in", ["outside_no_reason", "outside_with_reason"])],
        )

    def action_open_outside_missing_reason_visits(self):
        return self._action_open_geo_visits(
            _("Outside Zone - Missing Reason"),
            self._get_base_visit_domain(include_process_filter=False) + [("geo_review_state", "=", "outside_no_reason")],
        )

    def action_open_needs_review_visits(self):
        return self._action_open_geo_visits(
            _("Needs Supervisor Review"),
            self._get_base_visit_domain(include_process_filter=False) + [("geo_review_required", "=", True), ("geo_review_supervisor_decision", "=", False)],
        )

    def action_open_accepted_visits(self):
        return self._action_open_geo_visits(
            _("Accepted Geo Reviews"),
            self._get_base_visit_domain(include_process_filter=False) + [("geo_review_supervisor_decision", "=", "accepted")],
        )

    def action_open_needs_correction_visits(self):
        return self._action_open_geo_visits(
            _("Geo Reviews Needing Correction"),
            self._get_base_visit_domain(include_process_filter=False) + [("geo_review_supervisor_decision", "=", "needs_correction")],
        )

    def action_open_geo_review(self):
        return self._action_open_geo_visits(_("Geo Check-in Review Cards"), self._get_base_visit_domain(include_process_filter=False))
