from odoo import _, fields, models
from odoo.exceptions import ValidationError


class RouteVisitGeoReasonWizard(models.TransientModel):
    _name = "route.visit.geo.reason.wizard"
    _description = "Route Visit Geo Outside Zone Reason"

    visit_id = fields.Many2one(
        "route.visit",
        string="Visit",
        required=True,
        readonly=True,
    )
    outlet_id = fields.Many2one(
        related="visit_id.outlet_id",
        string="Outlet",
        readonly=True,
    )
    geo_checkin_status = fields.Selection(
        related="visit_id.geo_checkin_status",
        string="Geo Status",
        readonly=True,
    )
    geo_checkin_distance_display = fields.Char(
        related="visit_id.geo_checkin_distance_display",
        string="Distance from Outlet",
        readonly=True,
    )
    route_geo_checkin_radius_m = fields.Integer(
        related="visit_id.route_geo_checkin_radius_m",
        string="Allowed Radius (m)",
        readonly=True,
    )
    reason_code = fields.Selection(
        [
            ("customer_location_inaccurate", "Customer location is inaccurate"),
            ("gps_accuracy_issue", "GPS accuracy issue"),
            ("customer_met_outside_outlet", "Customer met outside outlet"),
            ("supervisor_approved", "Supervisor approved"),
            ("other", "Other"),
        ],
        string="Reason",
        required=True,
    )
    reason_note = fields.Text(
        string="Details",
        help="Optional operational note. Required when the selected reason is Other.",
    )

    def _prepare_reason_text(self):
        self.ensure_one()
        reason_labels = dict(self._fields["reason_code"].selection)
        reason = reason_labels.get(self.reason_code, self.reason_code or "")
        note = (self.reason_note or "").strip()
        if self.reason_code == "other" and not note:
            raise ValidationError(_("Please write the reason details when selecting Other."))
        if note:
            return "%s: %s" % (reason, note)
        return reason

    def action_confirm_and_start_visit(self):
        self.ensure_one()
        if not self.visit_id:
            raise ValidationError(_("Visit is required."))
        if self.visit_id.geo_checkin_status != "outside":
            return self.visit_id.with_context(route_geo_reason_confirmed=True).action_start_visit()

        self.visit_id.write({
            "geo_checkin_outside_zone_reason": self._prepare_reason_text(),
        })
        result = self.visit_id.with_context(route_geo_reason_confirmed=True).action_start_visit()
        if result:
            return result
        if hasattr(self.visit_id, "_get_pda_form_action"):
            return self.visit_id._get_pda_form_action()
        return {"type": "ir.actions.act_window_close"}
