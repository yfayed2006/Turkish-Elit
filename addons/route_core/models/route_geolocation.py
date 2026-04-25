from urllib.parse import quote_plus

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    route_enable_outlet_geolocation = fields.Boolean(
        string="Enable Outlet Geo Locations",
        compute="_compute_route_enable_outlet_geolocation",
        inverse="_inverse_route_enable_outlet_geolocation",
        readonly=False,
        help="Enable location fields and map actions for route outlets.",
    )
    route_map_provider = fields.Selection(
        [
            ("google", "Google Maps"),
            ("openstreetmap", "OpenStreetMap"),
            ("disabled", "Disabled"),
        ],
        string="Map Provider",
        compute="_compute_route_map_provider",
        inverse="_inverse_route_map_provider",
        readonly=False,
        help="Map provider used by Route Sales location buttons. Google Maps is used by default; OpenStreetMap can be selected for deployments that avoid Google services.",
    )
    route_google_maps_api_key = fields.Char(
        string="Google Maps API Key",
        compute="_compute_route_google_maps_api_key",
        inverse="_inverse_route_google_maps_api_key",
        readonly=False,
        help="Reserved for advanced map widgets and future live map screens. Basic Open in Maps buttons work without an API key.",
    )
    route_geo_checkin_radius_m = fields.Integer(
        string="Default Geo Check-in Radius (m)",
        compute="_compute_route_geo_checkin_radius_m",
        inverse="_inverse_route_geo_checkin_radius_m",
        readonly=False,
        help="Default allowed distance from outlet location for future Geo Check-in rules.",
    )
    route_geo_checkin_policy = fields.Selection(
        [
            ("disabled", "Disabled"),
            ("review_only", "Review Only"),
            ("require_reason", "Require Reason"),
            ("block_start", "Block Start"),
        ],
        string="Geo Check-in Policy",
        compute="_compute_route_geo_checkin_policy",
        inverse="_inverse_route_geo_checkin_policy",
        readonly=False,
        help="Controls how outside-zone check-ins will be handled. B4.1 only displays the selected policy; enforcement is introduced in the next phase.",
    )

    def _compute_route_enable_outlet_geolocation(self):
        for company in self:
            company.route_enable_outlet_geolocation = company._route_param_is_enabled(
                "enable_outlet_geolocation", default="1"
            )

    def _inverse_route_enable_outlet_geolocation(self):
        for company in self:
            company._set_route_param_enabled(
                "enable_outlet_geolocation", bool(company.route_enable_outlet_geolocation)
            )

    def _compute_route_map_provider(self):
        icp = self.env["ir.config_parameter"].sudo()
        allowed = {"google", "openstreetmap", "disabled"}
        for company in self:
            value = icp.get_param(company._route_feature_param_key("map_provider"), default="google")
            company.route_map_provider = value if value in allowed else "google"

    def _inverse_route_map_provider(self):
        icp = self.env["ir.config_parameter"].sudo()
        allowed = {"google", "openstreetmap", "disabled"}
        for company in self:
            value = company.route_map_provider or "google"
            if value not in allowed:
                value = "google"
            icp.set_param(company._route_feature_param_key("map_provider"), value)

    def _compute_route_google_maps_api_key(self):
        icp = self.env["ir.config_parameter"].sudo()
        for company in self:
            company.route_google_maps_api_key = icp.get_param(
                company._route_feature_param_key("google_maps_api_key"), default=""
            )

    def _inverse_route_google_maps_api_key(self):
        icp = self.env["ir.config_parameter"].sudo()
        for company in self:
            icp.set_param(
                company._route_feature_param_key("google_maps_api_key"),
                company.route_google_maps_api_key or "",
            )

    def _compute_route_geo_checkin_radius_m(self):
        icp = self.env["ir.config_parameter"].sudo()
        for company in self:
            value = icp.get_param(company._route_feature_param_key("geo_checkin_radius_m"), default="100")
            try:
                radius = int(value)
            except (TypeError, ValueError):
                radius = 100
            company.route_geo_checkin_radius_m = max(radius, 0)

    def _inverse_route_geo_checkin_radius_m(self):
        icp = self.env["ir.config_parameter"].sudo()
        for company in self:
            radius = max(int(company.route_geo_checkin_radius_m or 0), 0)
            icp.set_param(company._route_feature_param_key("geo_checkin_radius_m"), str(radius))


class RouteOutlet(models.Model):
    _inherit = "route.outlet"

    geo_latitude = fields.Float(
        string="Latitude",
        digits=(10, 7),
        help="Outlet GPS latitude used for route maps and future geo check-in.",
    )
    geo_longitude = fields.Float(
        string="Longitude",
        digits=(10, 7),
        help="Outlet GPS longitude used for route maps and future geo check-in.",
    )
    geo_address = fields.Char(
        string="Geo Address",
        help="Map/search address used for this outlet. When empty, the normal outlet address is used for map search.",
    )
    geo_place_id = fields.Char(
        string="Google Place ID",
        help="Optional Google Place ID reserved for future Google Maps integration.",
    )
    geo_accuracy_m = fields.Float(
        string="Geo Accuracy (m)",
        digits=(16, 2),
        help="Optional accuracy radius for the stored outlet coordinates.",
    )
    geo_source = fields.Selection(
        [
            ("manual", "Manual"),
            ("address", "Address Search"),
            ("google", "Google Maps"),
            ("import", "Import"),
        ],
        string="Geo Source",
        default="manual",
        help="How the outlet location was captured or maintained.",
    )
    geo_verified = fields.Boolean(
        string="Location Verified",
        help="Enable when the supervisor confirms that the saved coordinates represent the real outlet location.",
    )
    geo_last_update = fields.Datetime(
        string="Last Location Update",
        readonly=True,
    )
    geo_status = fields.Selection(
        [
            ("missing", "Missing"),
            ("unverified", "Unverified"),
            ("verified", "Verified"),
        ],
        string="Location Status",
        compute="_compute_geo_status",
        store=True,
    )
    geo_display_coordinates = fields.Char(
        string="Coordinates",
        compute="_compute_geo_display_coordinates",
    )

    @api.depends("geo_latitude", "geo_longitude", "geo_verified")
    def _compute_geo_status(self):
        for outlet in self:
            if not outlet._has_geo_coordinates():
                outlet.geo_status = "missing"
            elif outlet.geo_verified:
                outlet.geo_status = "verified"
            else:
                outlet.geo_status = "unverified"

    @api.depends("geo_latitude", "geo_longitude", "geo_status")
    def _compute_geo_display_coordinates(self):
        for outlet in self:
            if not outlet._has_geo_coordinates():
                outlet.geo_display_coordinates = False
            else:
                outlet.geo_display_coordinates = "%.6f, %.6f" % (outlet.geo_latitude, outlet.geo_longitude)

    @api.constrains("geo_latitude", "geo_longitude", "geo_accuracy_m")
    def _check_geo_values(self):
        for outlet in self:
            if outlet._has_geo_coordinates():
                if outlet.geo_latitude < -90.0 or outlet.geo_latitude > 90.0:
                    raise ValidationError(_("Latitude must be between -90 and 90."))
                if outlet.geo_longitude < -180.0 or outlet.geo_longitude > 180.0:
                    raise ValidationError(_("Longitude must be between -180 and 180."))
            if outlet.geo_accuracy_m and outlet.geo_accuracy_m < 0:
                raise ValidationError(_("Geo Accuracy cannot be negative."))

    @api.onchange("street", "street2", "city", "state_id", "country_id", "route_city_id", "area_id")
    def _onchange_geo_address_from_address(self):
        for outlet in self:
            if not outlet.geo_address:
                outlet.geo_address = outlet._get_outlet_map_query()

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            if any(key in vals for key in ("geo_latitude", "geo_longitude", "geo_address", "geo_place_id", "geo_accuracy_m")):
                vals.setdefault("geo_last_update", now)
                vals.setdefault("geo_source", "manual")
        return super().create(vals_list)

    def write(self, vals):
        geo_keys = {"geo_latitude", "geo_longitude", "geo_address", "geo_place_id", "geo_accuracy_m", "geo_verified", "geo_source"}
        if geo_keys.intersection(vals):
            vals = dict(vals)
            vals.setdefault("geo_last_update", fields.Datetime.now())
            if {"geo_latitude", "geo_longitude", "geo_place_id"}.intersection(vals) and "geo_verified" not in vals:
                vals["geo_verified"] = False
            if {"geo_latitude", "geo_longitude"}.intersection(vals) and "geo_source" not in vals:
                vals["geo_source"] = "manual"
        return super().write(vals)

    def _has_geo_coordinates(self):
        self.ensure_one()
        return bool(self.geo_latitude or self.geo_longitude)

    def _get_outlet_map_query(self):
        self.ensure_one()
        parts = [
            self.street,
            self.street2,
            self.city,
            self.state_id.name if self.state_id else False,
            self.country_id.name if self.country_id else False,
        ]
        if not any(parts):
            parts = [
                self.name,
                self.route_city_id.name if self.route_city_id else False,
                self.area_id.name if self.area_id else False,
                self.route_country_id.name if self.route_country_id else False,
            ]
        return ", ".join([part.strip() for part in parts if part and part.strip()])

    def _get_route_map_provider(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        provider = getattr(company, "route_map_provider", "google") or "google"
        return provider if provider in ("google", "openstreetmap", "disabled") else "google"

    def _get_map_url(self, mode="view"):
        self.ensure_one()
        provider = self._get_route_map_provider()
        if provider == "disabled":
            return False

        has_coordinates = self._has_geo_coordinates()
        latitude = self.geo_latitude or 0.0
        longitude = self.geo_longitude or 0.0
        query = self.geo_address or self._get_outlet_map_query() or self.name or ""

        if provider == "openstreetmap":
            if has_coordinates:
                return "https://www.openstreetmap.org/?mlat=%s&mlon=%s#map=18/%s/%s" % (
                    latitude,
                    longitude,
                    latitude,
                    longitude,
                )
            return "https://www.openstreetmap.org/search?query=%s" % quote_plus(query)

        if mode == "navigate" and has_coordinates:
            return "https://www.google.com/maps/dir/?api=1&destination=%s,%s" % (latitude, longitude)
        if has_coordinates:
            return "https://www.google.com/maps/search/?api=1&query=%s,%s" % (latitude, longitude)
        return "https://www.google.com/maps/search/?api=1&query=%s" % quote_plus(query)

    def _map_disabled_notification(self):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Map Provider Disabled"),
                "message": _("Enable a map provider in Route Settings before opening map links."),
                "sticky": False,
                "type": "warning",
            },
        }

    def action_open_outlet_map(self):
        self.ensure_one()
        url = self._get_map_url(mode="view")
        if not url:
            return self._map_disabled_notification()
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}

    def action_open_outlet_navigation(self):
        self.ensure_one()
        url = self._get_map_url(mode="navigate")
        if not url:
            return self._map_disabled_notification()
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}

    def action_search_outlet_address_on_map(self):
        self.ensure_one()
        provider = self._get_route_map_provider()
        if provider == "disabled":
            return self._map_disabled_notification()
        query = self.geo_address or self._get_outlet_map_query() or self.name or ""
        if provider == "openstreetmap":
            url = "https://www.openstreetmap.org/search?query=%s" % quote_plus(query)
        else:
            url = "https://www.google.com/maps/search/?api=1&query=%s" % quote_plus(query)
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}

    def action_verify_outlet_location(self):
        for outlet in self:
            if not outlet._has_geo_coordinates():
                raise ValidationError(_("Please set Latitude and Longitude before verifying the outlet location."))
        self.write({"geo_verified": True})
        return True

    def action_mark_outlet_location_unverified(self):
        self.write({"geo_verified": False})
        return True

    def action_clear_outlet_location(self):
        self.write({
            "geo_latitude": 0.0,
            "geo_longitude": 0.0,
            "geo_accuracy_m": 0.0,
            "geo_place_id": False,
            "geo_verified": False,
            "geo_source": "manual",
        })
        return True
