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
    route_city_id = fields.Many2one("route.city", string="Route City")
    area_id = fields.Many2one("route.area", string="Area")
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
                if not rec.city:
                    rec.city = rec.route_city_id.name
            if rec.area_id and rec.area_id.city_id != rec.route_city_id:
                rec.area_id = False

    @api.onchange("area_id")
    def _onchange_area_id(self):
        for rec in self:
            if rec.area_id:
                rec.route_city_id = rec.area_id.city_id
                rec.route_country_id = rec.area_id.country_id
                rec.route_area_name = rec.area_id.name
                if not rec.city and rec.route_city_id:
                    rec.city = rec.route_city_id.name

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
            has_existing_area = bool(record.area_id)
            has_new_area_details = bool(
                record.route_country_id
                and (record.route_city_id or (record.city or "").strip())
                and (record.route_area_name or "").strip()
            )
            if not (has_existing_area or has_new_area_details):
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

    def _action_open_salesperson_prospects(self):
        action_ref = self.env.ref("route_core.action_route_outlet_prospect_salesperson", raise_if_not_found=False)
        if action_ref:
            action = action_ref.read()[0]
        else:
            action = {
                "type": "ir.actions.act_window",
                "name": _("Potential Customers"),
                "res_model": "route.outlet.prospect",
                "view_mode": "kanban,list,form",
            }
        action["target"] = "main"
        action["domain"] = [
            ("salesperson_id", "=", self.env.user.id),
            ("state", "in", ["draft", "submitted", "needs_correction"]),
        ]
        action["context"] = dict(
            self.env.context,
            default_salesperson_id=self.env.user.id,
            search_default_filter_my_leads=1,
            route_pda_salesperson_form=1,
            create=True,
            edit=True,
            delete=False,
        )
        return action

    def action_noop_pending_review(self):
        return self._notify(_("Pending Review"), _("This potential customer is already waiting for supervisor review."), "info")

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
        return self._action_open_salesperson_prospects()

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

    def _filter_existing_fields(self, model_name, vals):
        """Keep the approval flow compatible with different Odoo/Odoo.sh editions.

        Some databases/customizations do not expose optional contact fields such as
        mobile on res.partner. Filtering prevents approval from failing with
        "Invalid field ..." while still passing every field that exists.
        """
        model_fields = self.env[model_name]._fields
        return {key: value for key, value in vals.items() if key in model_fields}

    def _get_or_create_route_city(self):
        self.ensure_one()
        if self.route_city_id:
            return self.route_city_id
        city_name = (self.city or "").strip()
        if not (self.route_country_id and city_name):
            return self.env["route.city"]
        city = self.env["route.city"].sudo().search([
            ("country_id", "=", self.route_country_id.id),
            ("name", "=ilike", city_name),
        ], limit=1)
        if city:
            return city
        return self.env["route.city"].sudo().create({
            "name": city_name,
            "country_id": self.route_country_id.id,
        })

    def _get_or_create_route_area(self):
        self.ensure_one()
        if self.area_id:
            return self.area_id
        city = self._get_or_create_route_city()
        area_name = (self.route_area_name or "").strip()
        if not (city and area_name):
            return self.env["route.area"]
        area = self.env["route.area"].sudo().search([
            ("city_id", "=", city.id),
            ("name", "=ilike", area_name),
        ], limit=1)
        if area:
            return area
        return self.env["route.area"].sudo().create({
            "name": area_name,
            "city_id": city.id,
        })

    def _prepare_partner_vals(self):
        self.ensure_one()
        route_city = self._get_or_create_route_city()
        route_area = self.area_id
        if not route_city and route_area:
            route_city = route_area.city_id
        route_country = self.route_country_id or (route_area.country_id if route_area else self.env["res.country"])
        vals = {
            "name": self.contact_name or self.name,
            "company_type": "company",
            "phone": self.phone or False,
            "mobile": self.mobile or False,
            "email": self.email or False,
            "street": self.street or False,
            "street2": self.street2 or False,
            "city": self.city or (route_city.name if route_city else False),
            "country_id": route_country.id if route_country else False,
            "company_id": self.company_id.id,
        }
        return self._filter_existing_fields("res.partner", vals)

    def _prepare_outlet_vals(self, partner, commercial_vals=None):
        self.ensure_one()
        route_city = self._get_or_create_route_city()
        route_area = self._get_or_create_route_area()
        if not route_city and route_area:
            route_city = route_area.city_id
        commercial_vals = dict(commercial_vals or {})
        vals = {
            "name": self.name,
            "partner_id": partner.id,
            "outlet_operation_mode": self.outlet_operation_mode,
            "phone": self.phone or False,
            "mobile": self.mobile or False,
            "street": self.street or False,
            "street2": self.street2 or False,
            "city": self.city or (route_city.name if route_city else False),
            "company_id": self.company_id.id,
            "note": self._build_outlet_note(),
        }
        if route_area:
            vals["area_id"] = route_area.id
            vals["route_area_name"] = route_area.name
        elif self.route_area_name:
            vals["route_area_name"] = self.route_area_name
        if self.route_country_id:
            vals["route_country_id"] = self.route_country_id.id
        elif route_area and route_area.country_id:
            vals["route_country_id"] = route_area.country_id.id
        if route_city:
            vals["route_city_id"] = route_city.id
        vals.update(commercial_vals)
        if "geo_latitude" in self.env["route.outlet"]._fields and self.location_captured:
            vals.update({
                "geo_latitude": self.latitude,
                "geo_longitude": self.longitude,
                "geo_accuracy_m": self.location_accuracy_m,
                "geo_source": "manual",
                "geo_verified": True,
            })
        return self._filter_existing_fields("route.outlet", vals)

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
        self.ensure_one()
        self._validate_approval_ready()
        wizard_vals = {
            "prospect_id": self.id,
            "outlet_operation_mode": self.outlet_operation_mode or "direct_sale",
        }
        if (self.outlet_operation_mode or "direct_sale") == "direct_sale":
            pricelist = self.env["product.pricelist"].search([], limit=1)
            if pricelist:
                wizard_vals["direct_sale_pricelist_id"] = pricelist.id
        wizard = self.env["route.outlet.prospect.approval.wizard"].create(wizard_vals)
        if wizard.outlet_operation_mode == "consignment" and wizard.consignment_commission_mode == "category_rate":
            wizard.write({"category_commission_line_ids": wizard._prepare_category_line_commands()})
        view = self.env.ref("route_core.view_route_outlet_prospect_approval_wizard_form", raise_if_not_found=False)
        return {
            "type": "ir.actions.act_window",
            "name": _("Approve Potential Customer"),
            "res_model": "route.outlet.prospect.approval.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "views": [(view.id, "form")] if view else [(False, "form")],
            "target": "new",
            "context": dict(self.env.context, default_prospect_id=self.id),
        }

    def _approve_and_create_outlet_from_setup(self, commercial_vals=None, commission_line_vals=None):
        self._validate_approval_ready()
        commercial_vals = dict(commercial_vals or {})
        commission_line_vals = list(commission_line_vals or [])
        OutletCommission = self.env["route.outlet.category.commission"].sudo()
        for record in self:
            partner = self.env["res.partner"].create(record._prepare_partner_vals())
            outlet = self.env["route.outlet"].create(record._prepare_outlet_vals(partner, commercial_vals=commercial_vals))
            if outlet.outlet_operation_mode == "consignment" and outlet.consignment_commission_mode == "category_rate":
                for line_vals in commission_line_vals:
                    vals = dict(line_vals)
                    vals["outlet_id"] = outlet.id
                    OutletCommission.create(vals)
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
        view_xmlid = "route_core.view_route_outlet_prospect_review_form" if self.env.context.get("route_pda_supervisor_form") else "route_core.view_route_outlet_prospect_form"
        view = self.env.ref(view_xmlid, raise_if_not_found=False)
        return {
            "type": "ir.actions.client",
            "tag": "route_core_capture_outlet_prospect_location",
            "params": {
                "prospect_id": self.id,
                "view_id": view.id if view else False,
                "context": {
                    "route_pda_salesperson_form": bool(self.env.context.get("route_pda_salesperson_form")),
                    "route_pda_supervisor_form": bool(self.env.context.get("route_pda_supervisor_form")),
                },
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

