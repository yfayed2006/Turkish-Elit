import math

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RouteVisit(models.Model):
    _inherit = "route.visit"

    route_geo_enabled = fields.Boolean(
        string="Visit Location Enabled",
        related="company_id.route_enable_outlet_geolocation",
        readonly=True,
        store=False,
    )
    route_geo_checkin_radius_m = fields.Integer(
        string="Allowed Check-in Radius (m)",
        related="company_id.route_geo_checkin_radius_m",
        readonly=True,
        store=False,
    )
    route_geo_checkin_policy = fields.Selection(
        related="company_id.route_geo_checkin_policy",
        string="Location Check-in Policy",
        readonly=True,
        store=False,
    )
    outlet_geo_status = fields.Selection(
        related="outlet_id.geo_status",
        string="Outlet Location Status",
        readonly=True,
        store=False,
    )
    outlet_geo_coordinates = fields.Char(
        related="outlet_id.geo_display_coordinates",
        string="Outlet Coordinates",
        readonly=True,
        store=False,
    )

    geo_checkin_latitude = fields.Float(
        string="Check-in Latitude",
        digits=(10, 7),
        copy=False,
        help="Location latitude captured at visit check-in. This foundation field does not block visit execution yet.",
    )
    geo_checkin_longitude = fields.Float(
        string="Check-in Longitude",
        digits=(10, 7),
        copy=False,
        help="Location longitude captured at visit check-in. This foundation field does not block visit execution yet.",
    )
    geo_checkin_accuracy_m = fields.Float(
        string="Check-in Accuracy (m)",
        digits=(16, 2),
        copy=False,
        help="Optional device accuracy reported with the check-in location.",
    )
    geo_checkin_datetime = fields.Datetime(
        string="Location Check-in Time",
        copy=False,
    )
    geo_checkin_distance_m = fields.Float(
        string="Distance from Outlet (m)",
        compute="_compute_geo_checkin_distance_and_status",
        digits=(16, 2),
        store=False,
    )
    geo_checkin_distance_display = fields.Char(
        string="Distance",
        compute="_compute_geo_checkin_distance_and_status",
        store=False,
    )
    geo_checkin_status = fields.Selection(
        [
            ("disabled", "Disabled"),
            ("outlet_missing", "Missing Location"),
            ("pending", "Pending"),
            ("inside", "Inside Zone"),
            ("outside", "Outside Zone"),
        ],
        string="Location Check-in Status",
        compute="_compute_geo_checkin_distance_and_status",
        store=False,
    )
    geo_checkin_outside_zone_reason = fields.Text(
        string="Outside Zone Reason",
        copy=False,
        help="Reserved for the next enforcement phase when a reason may be required for outside-zone check-ins.",
    )
    geo_review_state = fields.Selection(
        [
            ("disabled", "Disabled"),
            ("pending_checkin", "Pending Check-in"),
            ("outlet_missing", "Outlet Location Missing"),
            ("inside_zone", "Inside Zone"),
            ("outside_no_reason", "Outside - Missing Reason"),
            ("outside_with_reason", "Outside - Reason Recorded"),
        ],
        string="Location Review",
        compute="_compute_geo_review_fields",
        store=True,
        copy=False,
        index=True,
        help="Supervisor review status for visit location check-ins.",
    )
    geo_review_required = fields.Boolean(
        string="Needs Location Review",
        compute="_compute_geo_review_fields",
        store=True,
        copy=False,
        index=True,
    )
    geo_review_missing_reason = fields.Boolean(
        string="Missing Outside-Zone Reason",
        compute="_compute_geo_review_fields",
        store=True,
        copy=False,
        index=True,
    )
    geo_review_supervisor_decision = fields.Selection(
        [
            ("accepted", "Accepted"),
            ("needs_correction", "Needs Correction"),
        ],
        string="Supervisor Decision",
        copy=False,
        index=True,
        help="Supervisor decision for outside-zone or unusual location check-ins.",
    )
    geo_review_supervisor_note = fields.Text(
        string="Supervisor Review Note",
        copy=False,
        help="Optional supervisor note explaining the review decision or requested correction.",
    )
    geo_review_supervisor_user_id = fields.Many2one(
        "res.users",
        string="Reviewed By",
        readonly=True,
        copy=False,
        index=True,
    )
    geo_review_supervisor_datetime = fields.Datetime(
        string="Reviewed On",
        readonly=True,
        copy=False,
    )


    @api.depends(
        "company_id.route_enable_outlet_geolocation",
        "company_id.route_geo_checkin_radius_m",
        "outlet_id.geo_latitude",
        "outlet_id.geo_longitude",
        "geo_checkin_latitude",
        "geo_checkin_longitude",
    )
    def _compute_geo_checkin_distance_and_status(self):
        for visit in self:
            distance = 0.0
            status = "disabled"

            if not visit.route_geo_enabled:
                visit.geo_checkin_distance_m = distance
                visit.geo_checkin_distance_display = visit._format_geo_distance(distance)
                visit.geo_checkin_status = status
                continue

            if not visit._has_outlet_geo_coordinates():
                visit.geo_checkin_distance_m = distance
                visit.geo_checkin_distance_display = visit._format_geo_distance(distance)
                visit.geo_checkin_status = "outlet_missing"
                continue

            if not visit._has_geo_checkin_coordinates():
                visit.geo_checkin_distance_m = distance
                visit.geo_checkin_distance_display = visit._format_geo_distance(distance)
                visit.geo_checkin_status = "pending"
                continue

            distance = visit._geo_distance_meters(
                visit.geo_checkin_latitude,
                visit.geo_checkin_longitude,
                visit.outlet_id.geo_latitude,
                visit.outlet_id.geo_longitude,
            )
            radius = max(visit.route_geo_checkin_radius_m or 0, 0)
            status = "inside" if radius <= 0 or distance <= radius else "outside"

            visit.geo_checkin_distance_m = distance
            visit.geo_checkin_distance_display = visit._format_geo_distance(distance)
            visit.geo_checkin_status = status

    @api.depends(
        "company_id",
        "company_id.route_enable_outlet_geolocation",
        "company_id.route_geo_checkin_radius_m",
        "outlet_id.geo_latitude",
        "outlet_id.geo_longitude",
        "geo_checkin_latitude",
        "geo_checkin_longitude",
        "geo_checkin_outside_zone_reason",
    )
    def _compute_geo_review_fields(self):
        for visit in self:
            review_state = "disabled"
            review_required = False
            missing_reason = False

            if visit.route_geo_enabled:
                if not visit._has_outlet_geo_coordinates():
                    review_state = "outlet_missing"
                elif not visit._has_geo_checkin_coordinates():
                    review_state = "pending_checkin"
                else:
                    distance = visit._geo_distance_meters(
                        visit.geo_checkin_latitude,
                        visit.geo_checkin_longitude,
                        visit.outlet_id.geo_latitude,
                        visit.outlet_id.geo_longitude,
                    )
                    radius = max(visit.route_geo_checkin_radius_m or 0, 0)
                    if radius <= 0 or distance <= radius:
                        review_state = "inside_zone"
                    elif (visit.geo_checkin_outside_zone_reason or "").strip():
                        review_state = "outside_with_reason"
                        review_required = True
                    else:
                        review_state = "outside_no_reason"
                        review_required = True
                        missing_reason = True

            visit.geo_review_state = review_state
            visit.geo_review_required = review_required
            visit.geo_review_missing_reason = missing_reason

    def action_open_geo_review_visit(self):
        self.ensure_one()
        view = self.env.ref("route_core.view_route_visit_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": self.display_name or _("Visit"),
            "res_model": "route.visit",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
            "context": {
                "create": False,
                "edit": True,
            },
        }
        if view:
            action["views"] = [(view.id, "form")]
        return action

    def _get_pda_form_action(self):
        """Return the compact salesperson visit form with stable PDA context."""
        self.ensure_one()
        parent = getattr(super(), "_get_pda_form_action", None)
        action = parent() if parent else {}
        if not isinstance(action, dict):
            action = {}

        form_view = self.env.ref("route_core.view_route_visit_pda_form", raise_if_not_found=False)
        action_ref = self.env.ref("route_core.action_route_visit_pda_salesperson", raise_if_not_found=False)
        context = action.get("context") or {}
        if not isinstance(context, dict):
            context = {}
        context.update({
            "search_default_filter_my_visits": 1,
            "search_default_filter_today": 1,
            "pda_mode": True,
            "route_pda_salesperson_mode": True,
            "create": 0,
            "edit": 1,
            "delete": 0,
        })
        action.update({
            "type": "ir.actions.act_window",
            "name": _("Today's Visits"),
            "res_model": "route.visit",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
            "context": context,
        })
        if action_ref:
            action["id"] = action_ref.id
        if form_view:
            action["view_id"] = form_view.id
            action["views"] = [(form_view.id, "form")]
        return action

    def action_pda_back_route_workspace(self):
        self.ensure_one()
        return self.env["route.pda.home"].action_open_dashboard()

    def action_pda_back_today_route_map(self):
        self.ensure_one()
        return self.env["route.salesperson.route.map"].action_open_salesperson_today_route_map()

    def action_pda_back_today_visits(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        action = self.env.ref("route_core.action_route_visit_pda_salesperson", raise_if_not_found=False)
        domain = [("user_id", "=", self.env.user.id), ("date", "=", today)]
        context = {
            "search_default_filter_my_visits": 1,
            "search_default_filter_today": 1,
            "pda_mode": True,
            "route_pda_salesperson_mode": True,
            "create": 0,
            "edit": 1,
            "delete": 0,
        }
        if action:
            result = action.read()[0]
            result.update({
                "name": _("Today's Visits"),
                "domain": domain,
                "context": context,
                "target": "current",
            })
            return result
        return {
            "type": "ir.actions.act_window",
            "name": _("Today's Visits"),
            "res_model": "route.visit",
            "view_mode": "kanban,form,list",
            "domain": domain,
            "target": "current",
            "context": context,
        }

    def _geo_review_reset_supervisor_decision_values(self):
        """Return values used when a fresh check-in replaces the previous review context."""
        return {
            "geo_review_supervisor_decision": False,
            "geo_review_supervisor_note": False,
            "geo_review_supervisor_user_id": False,
            "geo_review_supervisor_datetime": False,
        }

    def _geo_review_refresh_action(self, message=False, notification_type="success"):
        """Refresh the current review screen without creating extra breadcrumbs.

        Kanban cards in the Visit Location Control need visible feedback after
        supervisor actions. Returning a notification with a reload makes the
        result clear on both desktop and mobile while keeping the existing
        Location Review list/form behavior unchanged.
        """
        if message:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Location Review"),
                    "message": message,
                    "type": notification_type,
                    "sticky": False,
                    "next": {"type": "ir.actions.client", "tag": "reload"},
                },
            }
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_geo_review_accept(self):
        for visit in self:
            if not visit.geo_review_required:
                raise ValidationError(_("Only visits that need geo review can be marked as accepted."))
        self.with_context(
            route_visit_force_write=True,
            bypass_daily_closing_lock=True,
        ).write({
            "geo_review_supervisor_decision": "accepted",
            "geo_review_supervisor_user_id": self.env.user.id,
            "geo_review_supervisor_datetime": fields.Datetime.now(),
        })
        return self._geo_review_refresh_action(_("Location review accepted."))

    def action_geo_review_needs_correction(self):
        for visit in self:
            if not visit.geo_review_required:
                raise ValidationError(_("Only visits that need geo review can be marked as needs correction."))
        self.with_context(
            route_visit_force_write=True,
            bypass_daily_closing_lock=True,
        ).write({
            "geo_review_supervisor_decision": "needs_correction",
            "geo_review_supervisor_user_id": self.env.user.id,
            "geo_review_supervisor_datetime": fields.Datetime.now(),
        })
        return self._geo_review_refresh_action(_("Location review marked as needs correction."), notification_type="warning")

    def action_geo_review_reset_decision(self):
        self.with_context(
            route_visit_force_write=True,
            bypass_daily_closing_lock=True,
        ).write(self._geo_review_reset_supervisor_decision_values())
        return self._geo_review_refresh_action(_("Location review decision reset."), notification_type="info")

    @api.constrains("geo_checkin_latitude", "geo_checkin_longitude", "geo_checkin_accuracy_m")
    def _check_geo_checkin_values(self):
        for visit in self:
            if visit._has_geo_checkin_coordinates():
                if visit.geo_checkin_latitude < -90.0 or visit.geo_checkin_latitude > 90.0:
                    raise ValidationError(_("Check-in Latitude must be between -90 and 90."))
                if visit.geo_checkin_longitude < -180.0 or visit.geo_checkin_longitude > 180.0:
                    raise ValidationError(_("Check-in Longitude must be between -180 and 180."))
            if visit.geo_checkin_accuracy_m and visit.geo_checkin_accuracy_m < 0:
                raise ValidationError(_("Check-in Accuracy cannot be negative."))

    def _has_outlet_geo_coordinates(self):
        self.ensure_one()
        return bool(
            self.outlet_id
            and hasattr(self.outlet_id, "geo_latitude")
            and (self.outlet_id.geo_latitude or self.outlet_id.geo_longitude)
        )

    def _has_geo_checkin_coordinates(self):
        self.ensure_one()
        return bool(self.geo_checkin_latitude or self.geo_checkin_longitude)

    @api.model
    def _geo_distance_meters(self, lat1, lon1, lat2, lon2):
        """Return Haversine distance in meters between two coordinates."""
        earth_radius_m = 6371000.0
        lat1_rad = math.radians(lat1 or 0.0)
        lon1_rad = math.radians(lon1 or 0.0)
        lat2_rad = math.radians(lat2 or 0.0)
        lon2_rad = math.radians(lon2 or 0.0)
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        a = (
            math.sin(dlat / 2.0) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return earth_radius_m * c

    def _format_geo_distance(self, distance_m):
        """Return a compact distance label for PDA cards and notifications."""
        distance_m = float(distance_m or 0.0)
        if distance_m >= 1000.0:
            return _("%s km") % ("{:,.2f}".format(distance_m / 1000.0))
        return _("%s m") % ("{:,.0f}".format(distance_m))

    def _geo_checkin_edit_allowed(self):
        """Location check-in is a visit-start audit record once the visit begins."""
        for visit in self:
            if visit.visit_process_state and visit.visit_process_state != "draft":
                raise ValidationError(
                    _("Location Check-in is locked after the visit starts. Ask a supervisor to correct the audit record if needed.")
                )
        return True

    def _geo_outlet_coordinate_shortcut_allowed(self):
        """Allow outlet-coordinate shortcut only for supervisor/management review flows.

        The PDA salesperson flow must always capture the actual device location.
        """
        if self.env.context.get("route_pda_salesperson_mode"):
            return False
        user = self.env.user
        return (
            user.has_group("route_core.group_route_supervisor")
            or user.has_group("route_core.group_route_management")
        )

    def action_geo_checkin_from_outlet_location(self):
        """Supervisor/test helper: copy outlet coordinates into the visit check-in fields.

        Salespeople must use Capture My Location so the audit trail records the actual device position.
        """
        if not self._geo_outlet_coordinate_shortcut_allowed():
            raise ValidationError(
                _("Use Outlet Coordinates is reserved for supervisors/managers. Please use Capture My Location on the device.")
            )
        self._geo_checkin_edit_allowed()
        now = fields.Datetime.now()
        for visit in self:
            if not visit.outlet_id:
                raise ValidationError(_("Please set an outlet before recording a location check-in."))
            if not visit._has_outlet_geo_coordinates():
                raise ValidationError(_("Please set outlet Latitude and Longitude before recording a location check-in."))
            vals = {
                "geo_checkin_latitude": visit.outlet_id.geo_latitude,
                "geo_checkin_longitude": visit.outlet_id.geo_longitude,
                "geo_checkin_accuracy_m": visit.outlet_id.geo_accuracy_m or 0.0,
                "geo_checkin_datetime": now,
            }
            vals.update(visit._geo_review_reset_supervisor_decision_values())
            visit.write(vals)
        return True

    def action_clear_geo_checkin_location(self):
        self._geo_checkin_edit_allowed()
        vals = {
            "geo_checkin_latitude": 0.0,
            "geo_checkin_longitude": 0.0,
            "geo_checkin_accuracy_m": 0.0,
            "geo_checkin_datetime": False,
            "geo_checkin_outside_zone_reason": False,
        }
        vals.update(self._geo_review_reset_supervisor_decision_values())
        self.write(vals)
        return True

    def action_open_visit_outlet_map(self):
        self.ensure_one()
        if not self.outlet_id:
            raise ValidationError(_("This visit has no outlet."))
        return self.outlet_id.action_open_outlet_map()

    def action_open_visit_outlet_navigation(self):
        self.ensure_one()
        if not self.outlet_id:
            raise ValidationError(_("This visit has no outlet."))
        return self.outlet_id.action_open_outlet_navigation()

    def action_open_visit_checkin_map(self):
        self.ensure_one()
        if not self._has_geo_checkin_coordinates():
            raise ValidationError(_("Please set Check-in Latitude and Longitude first."))
        url = "https://www.google.com/maps/search/?api=1&query=%s,%s" % (
            self.geo_checkin_latitude,
            self.geo_checkin_longitude,
        )
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}

    def action_capture_current_geo_checkin(self):
        """Ask the browser/mobile device to capture the salesperson's current GPS location.

        The actual location prompt runs in a small client action because Python cannot access
        the browser geolocation API directly. This remains foundation mode: it records
        the location and calculates inside/outside zone, but it does not block Start Visit.
        """
        self._geo_checkin_edit_allowed()
        self.ensure_one()
        if not self.route_geo_enabled:
            raise ValidationError(_("Visit location tracking is disabled in Route Settings."))
        pda_view = self.env.ref("route_core.view_route_visit_pda_form", raise_if_not_found=False)
        pda_action = self.env.ref("route_core.action_route_visit_pda_salesperson", raise_if_not_found=False)
        return {
            "type": "ir.actions.client",
            "name": _("Capture My Location"),
            "tag": "route_core_capture_geo_checkin",
            "target": "current",
            "params": {
                "visit_id": self.id,
                "visit_name": self.display_name,
                "view_id": pda_view.id if pda_view else False,
                "action_id": pda_action.id if pda_action else False,
                "return_action_name": _("Today's Visits"),
            },
        }

    def _is_geo_start_policy_active(self):
        """Return True when Start Visit should evaluate location check-in requirements."""
        self.ensure_one()
        if self.visit_process_state and self.visit_process_state != "draft":
            return False
        if not self.route_geo_enabled:
            return False
        policy = self.route_geo_checkin_policy or "disabled"
        if policy not in ("require_reason", "block_start"):
            return False
        # The outside-zone reason wizard confirms only the Require Reason policy.
        # Block Start remains strict even if a reason exists.
        if policy == "require_reason" and self.env.context.get("route_geo_reason_confirmed"):
            return False
        return True

    def _geo_start_missing_checkin_message(self):
        """Return a user-facing message when the active policy needs a check-in first."""
        self.ensure_one()
        if not self._is_geo_start_policy_active():
            return False
        if self.geo_checkin_status == "pending":
            return _("Please capture your location before starting the visit.")
        if self.geo_checkin_status == "outlet_missing":
            return _("Please set and verify the outlet location before starting the visit.")
        return False

    def _should_require_geo_reason_before_start(self):
        """Return True when Require Reason needs an outside-zone reason before Start Visit.

        `Require Reason` means a location check-in is required before Start Visit.
        If the check-in is outside the outlet radius, the salesperson must provide
        an operational reason before the visit can move to Checked In.
        """
        self.ensure_one()
        if not self._is_geo_start_policy_active():
            return False
        if self.route_geo_checkin_policy != "require_reason":
            return False
        if self.geo_checkin_status != "outside":
            return False
        return not bool((self.geo_checkin_outside_zone_reason or "").strip())

    def _should_block_geo_before_start(self):
        """Return True when Block Start policy forbids outside-zone visit starts."""
        self.ensure_one()
        if not self._is_geo_start_policy_active():
            return False
        if self.route_geo_checkin_policy != "block_start":
            return False
        return self.geo_checkin_status == "outside"

    def _action_open_geo_reason_wizard(self):
        self.ensure_one()
        view = self.env.ref("route_core.view_route_visit_geo_reason_wizard_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Outside Zone Reason"),
            "res_model": "route.visit.geo.reason.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_visit_id": self.id,
            },
        }
        if view:
            action["views"] = [(view.id, "form")]
        return action

    def action_start_visit(self):
        for visit in self:
            missing_message = visit._geo_start_missing_checkin_message()
            if missing_message:
                raise ValidationError(missing_message)
            if visit._should_block_geo_before_start():
                raise ValidationError(
                    _("You are outside the allowed outlet radius. This visit cannot start under the current Location Check-in policy.")
                )
            if visit._should_require_geo_reason_before_start():
                return visit._action_open_geo_reason_wizard()
        return super().action_start_visit()

    def action_ux_start_visit(self):
        self.ensure_one()
        action = self.action_start_visit()
        if isinstance(action, dict):
            return action
        if hasattr(self, "_get_pda_form_action"):
            return self._get_pda_form_action()
        return action

    def action_save_browser_geo_checkin(self, latitude, longitude, accuracy=0.0):
        """Save location coordinates captured by the browser/mobile device.

        This method is called from a browser client action. In salesperson/PDA mode,
        the visit form can be opened with restricted record rules, so the actual
        coordinate write is done with sudo after the visit-start lock check. This
        keeps the operational lock intact while avoiding RPC-only access failures
        when saving the GPS audit fields.
        """
        self._geo_checkin_edit_allowed()
        now = fields.Datetime.now()
        try:
            latitude = float(latitude)
            longitude = float(longitude)
            accuracy = float(accuracy or 0.0)
        except (TypeError, ValueError):
            raise ValidationError(_("Invalid location coordinates received from the device."))

        if latitude < -90.0 or latitude > 90.0:
            raise ValidationError(_("Captured Latitude must be between -90 and 90."))
        if longitude < -180.0 or longitude > 180.0:
            raise ValidationError(_("Captured Longitude must be between -180 and 180."))
        if accuracy < 0:
            accuracy = 0.0

        for visit in self:
            vals = {
                "geo_checkin_latitude": latitude,
                "geo_checkin_longitude": longitude,
                "geo_checkin_accuracy_m": accuracy,
                "geo_checkin_datetime": now,
            }
            vals.update(visit._geo_review_reset_supervisor_decision_values())
            visit.with_context(route_visit_force_write=True).sudo().write(vals)

        first = self[:1].sudo()
        if first:
            first.invalidate_recordset([
                "geo_checkin_latitude",
                "geo_checkin_longitude",
                "geo_checkin_accuracy_m",
                "geo_checkin_datetime",
                "geo_checkin_distance_m",
                "geo_checkin_distance_display",
                "geo_checkin_status",
                "geo_review_state",
                "geo_review_required",
                "geo_review_missing_reason",
            ])
        return {
            "status": first.geo_checkin_status if first else False,
            "distance_m": first.geo_checkin_distance_m if first else 0.0,
            "distance_display": first.geo_checkin_distance_display if first else False,
        }
