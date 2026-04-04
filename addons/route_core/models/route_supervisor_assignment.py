from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RouteSupervisorAssignment(models.Model):
    _name = "route.supervisor.assignment"
    _description = "Route Supervisor Assignment"
    _order = "sequence, id"

    name = fields.Char(string="Rule Name", compute="_compute_name", store=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    supervisor_user_id = fields.Many2one(
        "res.users",
        string="Supervisor",
        required=True,
        ondelete="restrict",
        help="Supervisor who should receive the WhatsApp settlement message when this rule matches.",
    )
    supervisor_partner_id = fields.Many2one(
        "res.partner",
        string="Supervisor Contact",
        compute="_compute_supervisor_contact_fields",
        readonly=True,
        store=False,
    )
    supervisor_mobile = fields.Char(
        string="Supervisor Mobile",
        compute="_compute_supervisor_contact_fields",
        readonly=True,
        store=False,
    )
    supervisor_phone = fields.Char(
        string="Supervisor Phone",
        compute="_compute_supervisor_contact_fields",
        readonly=True,
        store=False,
    )

    country_id = fields.Many2one(
        "res.country",
        string="Country",
        ondelete="restrict",
        index=True,
        help="Optional. Leave empty to match all countries.",
    )
    city_id = fields.Many2one(
        "route.city",
        string="City",
        ondelete="restrict",
        index=True,
        help="Optional. Leave empty to match all cities.",
    )
    area_id = fields.Many2one(
        "route.area",
        string="Area",
        ondelete="restrict",
        index=True,
        help="Optional. Leave empty to match all areas.",
    )
    salesperson_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        ondelete="restrict",
        index=True,
        help="Optional. Highest-priority match when a specific salesperson should report to a specific supervisor.",
    )
    vehicle_id = fields.Many2one(
        "route.vehicle",
        string="Vehicle",
        ondelete="restrict",
        index=True,
        help="Optional. Use when a vehicle should report to a specific supervisor.",
    )
    notes = fields.Text(string="Notes")
    scope_label = fields.Char(string="Scope", compute="_compute_scope_label", store=False)

    @api.depends("supervisor_user_id")
    def _compute_supervisor_contact_fields(self):
        for rec in self:
            partner = rec.supervisor_user_id.partner_id
            rec.supervisor_partner_id = partner
            rec.supervisor_mobile = (getattr(rec.supervisor_user_id, "mobile", False) or getattr(partner, "mobile", False) or "")
            rec.supervisor_phone = (getattr(rec.supervisor_user_id, "phone", False) or getattr(partner, "phone", False) or "")

    @api.depends(
        "supervisor_user_id",
        "country_id",
        "city_id",
        "area_id",
        "salesperson_id",
        "vehicle_id",
        "company_id",
    )
    def _compute_name(self):
        for rec in self:
            parts = []
            if rec.salesperson_id:
                parts.append(_("Salesperson: %s") % rec.salesperson_id.display_name)
            if rec.vehicle_id:
                parts.append(_("Vehicle: %s") % rec.vehicle_id.display_name)
            if rec.area_id:
                parts.append(_("Area: %s") % rec.area_id.display_name)
            elif rec.city_id:
                parts.append(_("City: %s") % rec.city_id.display_name)
            elif rec.country_id:
                parts.append(_("Country: %s") % rec.country_id.display_name)
            if not parts:
                parts.append(_("Default Fallback"))
            supervisor_name = rec.supervisor_user_id.display_name or _("Supervisor")
            company_name = rec.company_id.display_name or _("Company")
            rec.name = "%s / %s / %s" % (company_name, supervisor_name, " - ".join(parts))

    def _compute_scope_label(self):
        for rec in self:
            labels = []
            if rec.salesperson_id:
                labels.append(_("Salesperson"))
            if rec.vehicle_id:
                labels.append(_("Vehicle"))
            if rec.area_id:
                labels.append(_("Area"))
            elif rec.city_id:
                labels.append(_("City"))
            elif rec.country_id:
                labels.append(_("Country"))
            rec.scope_label = ", ".join(labels) if labels else _("Default Fallback")

    @api.onchange("country_id")
    def _onchange_country_id(self):
        for rec in self:
            if rec.city_id and rec.country_id and rec.city_id.country_id != rec.country_id:
                rec.city_id = False
                rec.area_id = False

    @api.onchange("city_id")
    def _onchange_city_id(self):
        for rec in self:
            if rec.city_id:
                rec.country_id = rec.city_id.country_id
            if rec.area_id and rec.area_id.city_id != rec.city_id:
                rec.area_id = False

    @api.onchange("area_id")
    def _onchange_area_id(self):
        for rec in self:
            if rec.area_id:
                rec.city_id = rec.area_id.city_id
                rec.country_id = rec.area_id.country_id

    @api.constrains("supervisor_user_id")
    def _check_supervisor_user_groups(self):
        for rec in self:
            user = rec.supervisor_user_id
            if user and not (user.has_group("route_core.group_route_supervisor") or user.has_group("route_core.group_route_management")):
                raise ValidationError(_("Supervisor must belong to Route Supervisor or Route Management."))

    @api.constrains("country_id", "city_id", "area_id")
    def _check_geo_consistency(self):
        for rec in self:
            if rec.city_id and rec.country_id and rec.city_id.country_id != rec.country_id:
                raise ValidationError(_("Selected city does not belong to the selected country."))
            if rec.area_id and rec.city_id and rec.area_id.city_id != rec.city_id:
                raise ValidationError(_("Selected area does not belong to the selected city."))
            if rec.area_id and rec.country_id and rec.area_id.country_id != rec.country_id:
                raise ValidationError(_("Selected area does not belong to the selected country."))

    @api.model
    def _match_visit_rules(self, visit):
        visit.ensure_one()
        outlet = visit.outlet_id
        country = outlet.route_country_id or getattr(outlet.area_id, "country_id", False) or outlet.country_id
        city = outlet.route_city_id or getattr(outlet.area_id, "city_id", False)
        area = visit.area_id or outlet.area_id
        salesperson = visit.user_id
        vehicle = visit.vehicle_id

        rules = self.sudo().search([
            ("active", "=", True),
            ("company_id", "=", visit.company_id.id),
        ], order="sequence asc, id asc")

        def _matches(rule):
            return (
                (not rule.country_id or (country and rule.country_id.id == country.id))
                and (not rule.city_id or (city and rule.city_id.id == city.id))
                and (not rule.area_id or (area and rule.area_id.id == area.id))
                and (not rule.salesperson_id or (salesperson and rule.salesperson_id.id == salesperson.id))
                and (not rule.vehicle_id or (vehicle and rule.vehicle_id.id == vehicle.id))
            )

        matched = rules.filtered(_matches)
        if not matched:
            return self.browse()

        def _score(rule):
            return (
                (32 if rule.salesperson_id else 0)
                + (16 if rule.vehicle_id else 0)
                + (8 if rule.area_id else 0)
                + (4 if rule.city_id else 0)
                + (2 if rule.country_id else 0)
            )

        ordered = sorted(matched, key=lambda rule: (-_score(rule), rule.sequence, rule.id))
        return self.browse(ordered[0].id) if ordered else self.browse()
