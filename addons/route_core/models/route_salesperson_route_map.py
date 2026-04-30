import time

from markupsafe import Markup

from odoo import _, api, fields, models


class RouteSalespersonRouteMap(models.TransientModel):
    _name = "route.salesperson.route.map"
    _description = "Salesperson Today's Route Map"
    _rec_name = "name"

    name = fields.Char(
        string="Name",
        default=lambda self: _("Today's Route Map"),
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        readonly=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
    )
    visit_date = fields.Date(
        string="Visit Date",
        required=True,
        default=fields.Date.context_today,
        readonly=True,
    )
    route_geo_enabled = fields.Boolean(
        string="Visit Location Enabled",
        related="company_id.route_enable_outlet_geolocation",
        readonly=True,
        store=False,
    )
    route_map_provider = fields.Selection(
        related="company_id.route_map_provider",
        string="Map Provider",
        readonly=True,
        store=False,
    )
    route_geo_checkin_policy = fields.Selection(
        related="company_id.route_geo_checkin_policy",
        string="Location Check-in Policy",
        readonly=True,
        store=False,
    )
    total_visit_count = fields.Integer(string="Today's Visits", compute="_compute_route_map")
    mapped_visit_count = fields.Integer(string="Mapped Visits", compute="_compute_route_map")
    missing_location_count = fields.Integer(string="Missing Outlet Location", compute="_compute_route_map")
    done_visit_count = fields.Integer(string="Done", compute="_compute_route_map")
    active_visit_count = fields.Integer(string="In Progress", compute="_compute_route_map")
    pending_visit_count = fields.Integer(string="Pending", compute="_compute_route_map")
    outside_zone_count = fields.Integer(string="Outside Zone", compute="_compute_route_map")
    inside_zone_count = fields.Integer(string="Inside Zone", compute="_compute_route_map")
    next_visit_label = fields.Char(string="Next Visit", compute="_compute_route_map")
    route_visit_ids = fields.Many2many(
        "route.visit",
        string="Today's Route Visits",
        compute="_compute_route_map",
        readonly=True,
    )
    route_map_iframe_html = fields.Html(
        string="Today's Route Map",
        compute="_compute_route_map",
        sanitize=False,
    )
    route_map_note = fields.Char(
        string="Map Note",
        compute="_compute_route_map",
    )

    def _get_visit_domain(self):
        self.ensure_one()
        return [
            ("company_id", "=", self.company_id.id or self.env.company.id),
            ("user_id", "=", self.user_id.id or self.env.user.id),
            ("date", "=", self.visit_date or fields.Date.context_today(self)),
        ]

    def _visit_has_outlet_point(self, visit):
        outlet = visit.outlet_id
        return bool(outlet and (outlet.geo_latitude or outlet.geo_longitude))

    def _visit_bucket(self, visit):
        process = visit.visit_process_state or False
        state = visit.state or False
        if state in ("done", "cancel", "cancelled") or process in ("done", "cancel"):
            return "done"
        if state == "in_progress" or process in ("checked_in", "counting", "reconciled", "collection_done", "ready_to_close"):
            return "active"
        return "pending"

    def _get_route_map_iframe_html(self):
        self.ensure_one()
        if not self.id:
            return ""
        url = "/route_core/pda/today_route_map/frame/%s?ts=%s" % (self.id, int(time.time()))
        return Markup(
            '<iframe src="%s" '
            'style="width:100%%; height:clamp(620px, 78vh, 780px); min-height:620px; border:0; border-radius:14px; background:#f5f6f7;" '
            'loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>' % url
        )

    @api.depends("company_id", "user_id", "visit_date")
    def _compute_route_map(self):
        Visit = self.env["route.visit"]
        for route_map in self:
            visits = Visit.search(route_map._get_visit_domain(), order="date asc, id asc")
            mapped = visits.filtered(lambda visit: route_map._visit_has_outlet_point(visit))
            missing = visits - mapped
            done = visits.filtered(lambda visit: route_map._visit_bucket(visit) == "done")
            active = visits.filtered(lambda visit: route_map._visit_bucket(visit) == "active")
            pending = visits - done - active
            outside = visits.filtered(lambda visit: getattr(visit, "geo_checkin_status", False) == "outside")
            inside = visits.filtered(lambda visit: getattr(visit, "geo_checkin_status", False) == "inside")
            next_visit = (pending or active or visits)[:1]

            route_map.total_visit_count = len(visits)
            route_map.mapped_visit_count = len(mapped)
            route_map.missing_location_count = len(missing)
            route_map.done_visit_count = len(done)
            route_map.active_visit_count = len(active)
            route_map.pending_visit_count = len(pending)
            route_map.outside_zone_count = len(outside)
            route_map.inside_zone_count = len(inside)
            route_map.route_visit_ids = [(6, 0, visits.ids)]
            route_map.next_visit_label = next_visit.outlet_id.display_name or next_visit.display_name if next_visit else _("No visit available")
            route_map.route_map_note = ""
            route_map.route_map_iframe_html = route_map._get_route_map_iframe_html()

    @api.model
    def action_open_salesperson_today_route_map(self):
        route_map = self.create(
            {
                "name": _("Today's Route Map"),
                "company_id": self.env.company.id,
                "user_id": self.env.user.id,
                "visit_date": fields.Date.context_today(self),
            }
        )
        view = self.env.ref("route_core.view_route_salesperson_route_map_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Today's Route Map"),
            "res_model": "route.salesperson.route.map",
            "res_id": route_map.id,
            "view_mode": "form",
            "target": "current",
            "context": {"create": False, "edit": False, "delete": False},
        }
        if view:
            action["view_id"] = view.id
            action["views"] = [(view.id, "form")]
        return action

    def action_back_to_workspace(self):
        self.ensure_one()
        return self.env["route.pda.home"].action_open_dashboard()

    def action_refresh_map(self):
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_open_today_visits(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_visit_pda", raise_if_not_found=False)
        domain = self._get_visit_domain()
        if action:
            result = action.read()[0]
            result.update(
                {
                    "name": _("Today's Visits"),
                    "domain": domain,
                    "context": {"search_default_filter_my_visits": 1, "search_default_filter_today": 1, "edit": 1},
                }
            )
            return result
        return {
            "type": "ir.actions.act_window",
            "name": _("Today's Visits"),
            "res_model": "route.visit",
            "view_mode": "kanban,list,form",
            "domain": domain,
            "context": {"create": False, "edit": True, "delete": False},
        }
