from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RouteSupervisorAssignment(models.Model):
    _name = "route.supervisor.assignment"
    _description = "Route Supervisor Assignment"
    _order = "sequence, id"

    name = fields.Char(required=True, string="Rule Name", default=lambda self: _("New Rule"))
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        ondelete="restrict",
    )
    supervisor_user_id = fields.Many2one(
        "res.users",
        string="Supervisor",
        required=True,
        ondelete="restrict",
    )
    supervisor_partner_id = fields.Many2one(
        "res.partner",
        string="Supervisor Contact",
        related="supervisor_user_id.partner_id",
        store=False,
        readonly=True,
    )
    supervisor_mobile = fields.Char(
        string="Supervisor Mobile",
        compute="_compute_supervisor_contact_numbers",
        store=False,
        readonly=True,
    )
    supervisor_phone = fields.Char(
        string="Supervisor Phone",
        compute="_compute_supervisor_contact_numbers",
        store=False,
        readonly=True,
    )
    supervisor_whatsapp = fields.Char(
        string="Supervisor WhatsApp",
        compute="_compute_supervisor_whatsapp",
        store=False,
        readonly=True,
    )
    salesperson_ids = fields.Many2many(
        "res.users",
        "route_supervisor_assignment_salesperson_rel",
        "assignment_id",
        "user_id",
        string="Salespersons",
        help="Leave empty to allow any salesperson that matches the other filters.",
    )
    vehicle_ids = fields.Many2many(
        "route.vehicle",
        "route_supervisor_assignment_vehicle_rel",
        "assignment_id",
        "vehicle_id",
        string="Vehicles",
        help="Leave empty to allow any vehicle.",
    )
    area_ids = fields.Many2many(
        "route.area",
        "route_supervisor_assignment_area_rel",
        "assignment_id",
        "area_id",
        string="Areas",
        help="Leave empty to allow any area. Any outlet in the selected areas will match automatically.",
    )
    city_ids = fields.Many2many(
        "route.city",
        "route_supervisor_assignment_city_rel",
        "assignment_id",
        "city_id",
        string="Cities",
        help="Leave empty to allow any city.",
    )
    country_ids = fields.Many2many(
        "res.country",
        "route_supervisor_assignment_country_rel",
        "assignment_id",
        "country_id",
        string="Countries",
        help="Leave empty to allow any country.",
    )
    scope = fields.Selection(
        [
            ("salesperson", "Salespersons"),
            ("vehicle", "Vehicles"),
            ("area", "Areas"),
            ("city", "Cities"),
            ("country", "Countries"),
            ("default", "Default Fallback"),
        ],
        string="Scope",
        compute="_compute_scope",
        store=False,
    )
    scope_label = fields.Char(string="Scope", compute="_compute_scope_label", store=False)
    note = fields.Text(string="Notes")

    @api.depends("supervisor_user_id", "supervisor_user_id.partner_id")
    def _compute_supervisor_contact_numbers(self):
        for rec in self:
            partner = rec.supervisor_user_id.partner_id
            mobile = False
            phone = False
            if partner:
                if "mobile" in partner._fields:
                    mobile = partner.mobile
                if "phone" in partner._fields:
                    phone = partner.phone
            rec.supervisor_mobile = mobile or False
            rec.supervisor_phone = phone or False

    @api.depends("supervisor_user_id", "supervisor_user_id.partner_id")
    def _compute_supervisor_whatsapp(self):
        for rec in self:
            partner = rec.supervisor_user_id.partner_id
            mobile = False
            phone = False
            if partner:
                if "mobile" in partner._fields:
                    mobile = partner.mobile
                if "phone" in partner._fields:
                    phone = partner.phone
            rec.supervisor_whatsapp = mobile or phone or False

    @api.depends("salesperson_ids", "vehicle_ids", "area_ids", "city_ids", "country_ids")
    def _compute_scope(self):
        for rec in self:
            rec.scope = rec._get_scope_key()

    @api.depends("scope")
    def _compute_scope_label(self):
        labels = dict(self._fields["scope"].selection)
        for rec in self:
            rec.scope_label = labels.get(rec.scope, False)

    @api.onchange(
        "company_id",
        "supervisor_user_id",
        "salesperson_ids",
        "vehicle_ids",
        "area_ids",
        "city_ids",
        "country_ids",
    )
    def _onchange_assignment_name(self):
        for rec in self:
            if not rec.name or rec.name == _("New Rule"):
                rec.name = rec._build_assignment_name_from_records()

    @api.constrains("supervisor_user_id")
    def _check_supervisor_role(self):
        supervisor_group = self.env.ref("route_core.group_route_supervisor", raise_if_not_found=False)
        management_group = self.env.ref("route_core.group_route_management", raise_if_not_found=False)
        for rec in self:
            user = rec.supervisor_user_id
            if not user:
                continue
            is_supervisor = bool(supervisor_group and user in supervisor_group.users)
            is_management = bool(management_group and user in management_group.users)
            if not (is_supervisor or is_management):
                raise ValidationError(_("Supervisor must belong to Route Supervisor or Route Management."))

    @api.model_create_multi
    def create(self, vals_list):
        new_rule = _("New Rule")
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == new_rule:
                vals["name"] = self._build_assignment_name_from_values(vals)
        return super().create(vals_list)

    def write(self, vals):
        new_rule = _("New Rule")
        result = super().write(vals)
        trigger_fields = {
            "company_id",
            "supervisor_user_id",
            "salesperson_ids",
            "vehicle_ids",
            "area_ids",
            "city_ids",
            "country_ids",
        }
        if trigger_fields.intersection(vals):
            for rec in self:
                if not rec.name or rec.name == new_rule:
                    super(RouteSupervisorAssignment, rec).write({"name": rec._build_assignment_name_from_records()})
        return result

    def _get_scope_key(self):
        self.ensure_one()
        if self.salesperson_ids:
            return "salesperson"
        if self.vehicle_ids:
            return "vehicle"
        if self.area_ids:
            return "area"
        if self.city_ids:
            return "city"
        if self.country_ids:
            return "country"
        return "default"

    def _match_dimension_count(self):
        self.ensure_one()
        return sum(
            1
            for field_name in ("salesperson_ids", "vehicle_ids", "area_ids", "city_ids", "country_ids")
            if self[field_name]
        )

    def _build_assignment_name_from_records(self):
        self.ensure_one()
        parts = []
        if self.company_id:
            parts.append(self.company_id.display_name)
        if self.supervisor_user_id:
            parts.append(self.supervisor_user_id.display_name)
        filters = []
        if self.salesperson_ids:
            filters.append(_("Salespersons: %s") % self._short_names(self.salesperson_ids))
        if self.vehicle_ids:
            filters.append(_("Vehicles: %s") % self._short_names(self.vehicle_ids))
        if self.area_ids:
            filters.append(_("Areas: %s") % self._short_names(self.area_ids))
        if self.city_ids:
            filters.append(_("Cities: %s") % self._short_names(self.city_ids))
        if self.country_ids:
            filters.append(_("Countries: %s") % self._short_names(self.country_ids))
        if not filters:
            filters.append(_("Default Fallback"))
        parts.append(" - ".join(filters))
        return " / ".join([p for p in parts if p]) or _("New Rule")

    @api.model
    def _records_from_commands(self, model_name, commands):
        if not commands:
            return self.env[model_name]
        record_ids = []
        for command in commands:
            if not isinstance(command, (list, tuple)) or not command:
                continue
            if command[0] == 6:
                record_ids.extend(command[2] or [])
            elif command[0] == 4 and len(command) > 1:
                record_ids.append(command[1])
        return self.env[model_name].browse(record_ids)

    @api.model
    def _short_names(self, records, limit=3):
        names = records.mapped("display_name")
        if not names:
            return _("All")
        if len(names) <= limit:
            return ", ".join(names)
        return _("%s (+%s more)") % (", ".join(names[:limit]), len(names) - limit)

    @api.model
    def _build_assignment_name_from_values(self, vals):
        company = self.env["res.company"].browse(vals.get("company_id")) if vals.get("company_id") else self.env.company
        supervisor = self.env["res.users"].browse(vals.get("supervisor_user_id")) if vals.get("supervisor_user_id") else self.env.user
        salespersons = self._records_from_commands("res.users", vals.get("salesperson_ids"))
        vehicles = self._records_from_commands("route.vehicle", vals.get("vehicle_ids"))
        areas = self._records_from_commands("route.area", vals.get("area_ids"))
        cities = self._records_from_commands("route.city", vals.get("city_ids"))
        countries = self._records_from_commands("res.country", vals.get("country_ids"))

        parts = [company.display_name, supervisor.display_name]
        filters = []
        if salespersons:
            filters.append(_("Salespersons: %s") % self._short_names(salespersons))
        if vehicles:
            filters.append(_("Vehicles: %s") % self._short_names(vehicles))
        if areas:
            filters.append(_("Areas: %s") % self._short_names(areas))
        if cities:
            filters.append(_("Cities: %s") % self._short_names(cities))
        if countries:
            filters.append(_("Countries: %s") % self._short_names(countries))
        if not filters:
            filters.append(_("Default Fallback"))
        parts.append(" - ".join(filters))
        return " / ".join([p for p in parts if p]) or _("New Rule")

    def _get_visit_city_country(self, visit):
        self.ensure_one()
        area = visit.area_id or visit.outlet_id.area_id
        city = area.city_id if area else self.env["route.city"]
        country = area.country_id if area else self.env["res.country"]
        if not country and city:
            country = city.country_id
        return city, country

    def _matches_visit(self, visit):
        self.ensure_one()
        if self.company_id and visit.company_id and self.company_id != visit.company_id:
            return False

        city, country = self._get_visit_city_country(visit)

        if self.salesperson_ids and visit.user_id not in self.salesperson_ids:
            return False
        if self.vehicle_ids and visit.vehicle_id not in self.vehicle_ids:
            return False
        if self.area_ids and visit.area_id not in self.area_ids:
            return False
        if self.city_ids and city not in self.city_ids:
            return False
        if self.country_ids and country not in self.country_ids:
            return False
        return True

    def _priority_key(self):
        self.ensure_one()
        scope_order = {
            "salesperson": 0,
            "vehicle": 1,
            "area": 2,
            "city": 3,
            "country": 4,
            "default": 5,
        }
        return (
            scope_order.get(self._get_scope_key(), 99),
            -self._match_dimension_count(),
            self.sequence,
            self.id,
        )

    @api.model
    def _get_best_assignment_for_visit(self, visit):
        if not visit:
            return self.browse()

        domain = [("active", "=", True)]
        if visit.company_id:
            domain.append(("company_id", "=", visit.company_id.id))
        candidates = self.sudo().search(domain, order="sequence, id")
        matches = candidates.filtered(lambda rec: rec._matches_visit(visit))
        if not matches:
            return self.browse()
        best = sorted(matches, key=lambda rec: rec._priority_key())[0]
        return self.browse(best.id)
