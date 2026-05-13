from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RouteOutletProspect(models.Model):
    _name = "route.outlet.prospect"
    _description = "Potential Route Customer"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "submitted_at desc, create_date desc, id desc"

    name = fields.Char(string="Outlet Name", required=True, tracking=True)
    reference = fields.Char(string="Reference", default="New", copy=False, readonly=True, tracking=True)
    active = fields.Boolean(default=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("needs_correction", "Needs Correction"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )

    salesperson_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        default=lambda self: self.env.user,
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", readonly=True)
    reviewed_by_id = fields.Many2one("res.users", string="Reviewed By", readonly=True)
    submitted_at = fields.Datetime(string="Submitted At", readonly=True)
    reviewed_at = fields.Datetime(string="Reviewed At", readonly=True)

    outlet_operation_mode = fields.Selection(
        [
            ("direct_sale", "Direct Sale"),
            ("consignment", "Consignment"),
        ],
        string="Suggested Operation Mode",
        default="direct_sale",
        required=True,
    )

    contact_name = fields.Char(string="Contact Person")
    phone = fields.Char(string="Phone")
    mobile = fields.Char(string="Mobile")
    email = fields.Char(string="Email")

    route_country_id = fields.Many2one("res.country", string="Route Country")
    route_city_id = fields.Many2one("route.city", string="Route City", domain="[('country_id', '=', route_country_id)]")
    area_id = fields.Many2one("route.area", string="Area", domain="[('city_id', '=', route_city_id)]")
    route_area_name = fields.Char(string="Area Name")
    street = fields.Char(string="Street / Address Line 1")
    street2 = fields.Char(string="Address Line 2")
    city = fields.Char(string="City Text")
    display_address = fields.Char(string="Display Address", compute="_compute_display_address")

    shop_area_sqm = fields.Float(string="Approx. Shop Area (m²)", digits=(16, 2))
    frontage_width_m = fields.Float(string="Frontage Width (m)", digits=(16, 2))
    street_width_m = fields.Float(string="Street Width (m)", digits=(16, 2))
    entrance_width_m = fields.Float(string="Entrance Width (m)", digits=(16, 2))
    shelf_capacity_note = fields.Char(string="Shelf / Display Capacity")
    visibility_level = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
        ],
        string="Street Visibility",
        default="medium",
    )
    traffic_level = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
        ],
        string="Street Traffic",
        default="medium",
    )
    refrigeration_available = fields.Boolean(string="Refrigeration Available")
    parking_available = fields.Boolean(string="Parking Available")
    expected_monthly_sales = fields.Monetary(string="Expected Monthly Sales", currency_field="currency_id")
    product_interest_text = fields.Text(string="Suggested Products / Demand")
    competitor_notes = fields.Text(string="Nearby Competitors")
    salesperson_note = fields.Text(string="Salesperson Notes")
    supervisor_note = fields.Text(string="Supervisor Notes")

    exterior_image = fields.Image(string="Exterior Photo", max_width=1600, max_height=1600)
    interior_image = fields.Image(string="Interior Photo", max_width=1600, max_height=1600)

    latitude = fields.Float(string="Latitude", digits=(10, 7), readonly=True)
    longitude = fields.Float(string="Longitude", digits=(10, 7), readonly=True)
    location_accuracy_m = fields.Float(string="GPS Accuracy (m)", digits=(16, 2), readonly=True)
    location_captured_at = fields.Datetime(string="Location Captured At", readonly=True)
    location_captured = fields.Boolean(string="Location Captured", compute="_compute_location_captured")

    approved_partner_id = fields.Many2one("res.partner", string="Created Customer", readonly=True)
    approved_outlet_id = fields.Many2one("route.outlet", string="Created Outlet", readonly=True)

    @api.depends("street", "street2", "city", "route_city_id", "area_id")
    def _compute_display_address(self):
        for record in self:
            parts = [
                record.street or "",
                record.street2 or "",
                record.city or (record.route_city_id.name if record.route_city_id else ""),
                record.area_id.name if record.area_id else (record.route_area_name or ""),
            ]
            record.display_address = ", ".join([part for part in parts if part])

    @api.depends("latitude", "longitude")
    def _compute_location_captured(self):
        for record in self:
            record.location_captured = bool(record.latitude or record.longitude)

    @api.onchange("route_country_id")
    def _onchange_route_country_id(self):
        for rec in self:
            if rec.route_city_id and rec.route_city_id.country_id != rec.route_country_id:
                rec.route_city_id = False
            if rec.area_id and rec.area_id.country_id != rec.route_country_id:
                rec.area_id = False

    @api.onchange("route_city_id")
    def _onchange_route_city_id(self):
        for rec in self:
            if rec.route_city_id:
                rec.route_country_id = rec.route_city_id.country_id
            if rec.area_id and rec.area_id.city_id != rec.route_city_id:
                rec.area_id = False

    @api.onchange("area_id")
    def _onchange_area_id(self):
        for rec in self:
            if rec.area_id:
                rec.route_city_id = rec.area_id.city_id
                rec.route_country_id = rec.area_id.country_id
                rec.route_area_name = rec.area_id.name

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if not record.reference or record.reference == "New":
                record.reference = "LEAD/%05d" % record.id
        return records

    def write(self, vals):
        locked = self.filtered(lambda r: r.state in ("approved", "rejected", "cancelled"))
        editable_after_close = {"active", "message_follower_ids", "message_ids", "activity_ids"}
        if locked and any(key not in editable_after_close for key in vals):
            raise UserError(_("Approved, rejected, or cancelled potential customers cannot be edited."))
        return super().write(vals)

    def _validate_submit_ready(self):
        for record in self:
            if not record.name:
                raise ValidationError(_("Outlet Name is required."))
            if not (record.phone or record.mobile):
                raise ValidationError(_("Please enter at least one contact number before submitting."))

    def _validate_approval_ready(self):
        for record in self:
            if record.state != "submitted":
                raise UserError(_("Only submitted potential customers can be approved."))
            if not (record.area_id or (record.route_country_id and record.route_city_id and record.route_area_name)):
                raise ValidationError(_("Please select Area, or select Route Country, Route City, and enter Area Name before approval."))
            if record.outlet_operation_mode == "direct_sale" and not (record.contact_name or record.name):
                raise ValidationError(_("Customer name is required before creating a direct-sale outlet."))

    def _notify(self, title, message, notif_type="success", sticky=False, next_action=None):
        params = {
            "title": title,
            "message": message,
            "type": notif_type,
            "sticky": sticky,
        }
        if next_action:
            params["next"] = next_action
        return {"type": "ir.actions.client", "tag": "display_notification", "params": params}

    def action_submit(self):
        self._validate_submit_ready()
        for record in self:
            if record.state not in ("draft", "needs_correction"):
                raise UserError(_("Only draft or correction-needed potential customers can be submitted."))
            record.write({
                "state": "submitted",
                "submitted_at": fields.Datetime.now(),
            })
            record.message_post(body=_("Potential customer submitted for supervisor approval."))
        return self._notify(
            _("Submitted"),
            _("The potential customer was submitted to supervisor review."),
        )

    def action_request_correction(self):
        for record in self:
            if record.state != "submitted":
                raise UserError(_("Only submitted potential customers can be returned for correction."))
            record.write({
                "state": "needs_correction",
                "reviewed_by_id": self.env.user.id,
                "reviewed_at": fields.Datetime.now(),
            })
            record.message_post(body=_("Supervisor requested correction."))
        return self._notify(_("Correction Requested"), _("The potential customer was returned to the salesperson for correction."), "warning")

    def action_reject(self):
        for record in self:
            if record.state not in ("submitted", "needs_correction"):
                raise UserError(_("Only submitted or correction-needed potential customers can be rejected."))
            record.write({
                "state": "rejected",
                "reviewed_by_id": self.env.user.id,
                "reviewed_at": fields.Datetime.now(),
            })
            record.message_post(body=_("Potential customer rejected."))
        return self._notify(_("Rejected"), _("The potential customer was rejected."), "warning")

    def action_cancel(self):
        for record in self:
            if record.state not in ("draft", "needs_correction"):
                raise UserError(_("Only draft or correction-needed potential customers can be cancelled by the salesperson."))
            record.write({"state": "cancelled"})
            record.message_post(body=_("Potential customer cancelled."))
        return self._notify(_("Cancelled"), _("The potential customer was cancelled."), "warning")

    def action_reset_to_draft(self):
        for record in self:
            if record.state not in ("needs_correction", "rejected", "cancelled"):
                raise UserError(_("Only correction-needed, rejected, or cancelled potential customers can be reset to draft."))
            record.write({"state": "draft"})
        return self._notify(_("Reset"), _("The potential customer was reset to draft."))

    def _prepare_partner_vals(self):
        self.ensure_one()
        return {
            "name": self.contact_name or self.name,
            "company_type": "company",
            "phone": self.phone or False,
            "mobile": self.mobile or False,
            "email": self.email or False,
            "street": self.street or False,
            "street2": self.street2 or False,
            "city": self.city or (self.route_city_id.name if self.route_city_id else False),
            "company_id": self.company_id.id,
        }

    def _prepare_outlet_vals(self, partner):
        self.ensure_one()
        vals = {
            "name": self.name,
            "partner_id": partner.id,
            "outlet_operation_mode": self.outlet_operation_mode,
            "phone": self.phone or False,
            "mobile": self.mobile or False,
            "street": self.street or False,
            "street2": self.street2 or False,
            "city": self.city or (self.route_city_id.name if self.route_city_id else False),
            "company_id": self.company_id.id,
            "note": self._build_outlet_note(),
        }
        if self.area_id:
            vals["area_id"] = self.area_id.id
        if self.route_country_id:
            vals["route_country_id"] = self.route_country_id.id
        if self.route_city_id:
            vals["route_city_id"] = self.route_city_id.id
        if self.route_area_name:
            vals["route_area_name"] = self.route_area_name
        if "geo_latitude" in self.env["route.outlet"]._fields and self.location_captured:
            vals.update({
                "geo_latitude": self.latitude,
                "geo_longitude": self.longitude,
                "geo_accuracy_m": self.location_accuracy_m,
                "geo_source": "manual",
                "geo_verified": True,
            })
        return vals

    def _build_outlet_note(self):
        self.ensure_one()
        lines = [
            _("Created from potential customer lead: %s") % (self.reference or self.display_name),
            _("Submitted by: %s") % (self.salesperson_id.display_name or "-"),
        ]
        if self.shop_area_sqm:
            lines.append(_("Approx. shop area: %.2f m²") % self.shop_area_sqm)
        if self.frontage_width_m:
            lines.append(_("Frontage width: %.2f m") % self.frontage_width_m)
        if self.street_width_m:
            lines.append(_("Street width: %.2f m") % self.street_width_m)
        if self.entrance_width_m:
            lines.append(_("Entrance width: %.2f m") % self.entrance_width_m)
        if self.shelf_capacity_note:
            lines.append(_("Shelf/display capacity: %s") % self.shelf_capacity_note)
        if self.product_interest_text:
            lines.append(_("Suggested products/demand: %s") % self.product_interest_text)
        if self.competitor_notes:
            lines.append(_("Nearby competitors: %s") % self.competitor_notes)
        if self.salesperson_note:
            lines.append(_("Salesperson notes: %s") % self.salesperson_note)
        if self.supervisor_note:
            lines.append(_("Supervisor notes: %s") % self.supervisor_note)
        return "\n".join(lines)

    def action_approve(self):
        self._validate_approval_ready()
        for record in self:
            partner = self.env["res.partner"].create(record._prepare_partner_vals())
            outlet = self.env["route.outlet"].create(record._prepare_outlet_vals(partner))
            record.write({
                "state": "approved",
                "approved_partner_id": partner.id,
                "approved_outlet_id": outlet.id,
                "reviewed_by_id": self.env.user.id,
                "reviewed_at": fields.Datetime.now(),
            })
            record.message_post(body=_("Potential customer approved and outlet created: %s") % outlet.display_name)
            view = self.env.ref("route_core.view_route_outlet_financial_profile_form", raise_if_not_found=False)
            action = {
                "type": "ir.actions.act_window",
                "name": _("Customer Profile"),
                "res_model": "route.outlet",
                "res_id": outlet.id,
                "view_mode": "form",
                "target": "main",
                "context": {"create": 0, "edit": 0, "delete": 0},
            }
            if view:
                action["views"] = [(view.id, "form")]
            return action
        return {"type": "ir.actions.act_window_close"}

    def action_capture_location(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "route_core_capture_outlet_prospect_location",
            "params": {
                "prospect_id": self.id,
                "view_id": self.env.ref("route_core.view_route_outlet_prospect_form", raise_if_not_found=False).id if self.env.ref("route_core.view_route_outlet_prospect_form", raise_if_not_found=False) else False,
            },
        }

    @api.model
    def action_save_browser_location(self, prospect_id, latitude, longitude, accuracy=0.0):
        prospect = self.browse(prospect_id).exists()
        if not prospect:
            raise UserError(_("Potential customer was not found."))
        if prospect.state not in ("draft", "needs_correction"):
            raise UserError(_("Location can only be captured before supervisor approval."))
        latitude = float(latitude or 0.0)
        longitude = float(longitude or 0.0)
        if latitude < -90.0 or latitude > 90.0:
            raise ValidationError(_("Latitude must be between -90 and 90."))
        if longitude < -180.0 or longitude > 180.0:
            raise ValidationError(_("Longitude must be between -180 and 180."))
        prospect.write({
            "latitude": latitude,
            "longitude": longitude,
            "location_accuracy_m": float(accuracy or 0.0),
            "location_captured_at": fields.Datetime.now(),
        })
        return {"success": True}

    def action_open_captured_location_map(self):
        self.ensure_one()
        if not self.location_captured:
            raise UserError(_("No captured GPS location is available."))
        return {
            "type": "ir.actions.act_url",
            "url": "https://www.google.com/maps/search/?api=1&query=%s,%s" % (self.latitude, self.longitude),
            "target": "new",
        }

    def action_back_to_customer_profiles(self):
        self.ensure_one()
        home = self.env["route.pda.home"].create({})
        home._refresh_dashboard_snapshot()
        view = self.env.ref("route_core.view_route_pda_outlet_center_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Customer Profiles"),
            "res_model": "route.pda.home",
            "res_id": home.id,
            "view_mode": "form",
            "target": "main",
            "context": {"create": 0, "edit": 0, "delete": 0},
        }
        if view:
            action["views"] = [(view.id, "form")]
        return action
