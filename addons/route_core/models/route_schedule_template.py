from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from .route_schedule_common import (
    WEEKDAY_SELECTION,
    WEEKDAY_LABELS,
    compute_week_start_date,
)


class RouteScheduleTemplate(models.Model):
    _name = "route.schedule.template"
    _description = "Route Schedule Template"
    _order = "name"

    name = fields.Char(string="Template Name", required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        readonly=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        required=True,
    )
    vehicle_id = fields.Many2one(
        "route.vehicle",
        string="Vehicle",
        required=True,
        ondelete="restrict",
    )
    source_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Source Warehouse",
        domain="[('company_id', 'in', [False, company_id])]",
        default=lambda self: self.env.company.route_default_source_warehouse_id,
    )
    line_ids = fields.One2many(
        "route.schedule.template.line",
        "template_id",
        string="Weekly Stops",
    )
    monday_line_ids = fields.One2many(
        "route.schedule.template.line",
        "template_id",
        string="Monday Stops",
        domain=[("weekday", "=", "monday")],
    )
    tuesday_line_ids = fields.One2many(
        "route.schedule.template.line",
        "template_id",
        string="Tuesday Stops",
        domain=[("weekday", "=", "tuesday")],
    )
    wednesday_line_ids = fields.One2many(
        "route.schedule.template.line",
        "template_id",
        string="Wednesday Stops",
        domain=[("weekday", "=", "wednesday")],
    )
    thursday_line_ids = fields.One2many(
        "route.schedule.template.line",
        "template_id",
        string="Thursday Stops",
        domain=[("weekday", "=", "thursday")],
    )
    friday_line_ids = fields.One2many(
        "route.schedule.template.line",
        "template_id",
        string="Friday Stops",
        domain=[("weekday", "=", "friday")],
    )
    saturday_line_ids = fields.One2many(
        "route.schedule.template.line",
        "template_id",
        string="Saturday Stops",
        domain=[("weekday", "=", "saturday")],
    )
    sunday_line_ids = fields.One2many(
        "route.schedule.template.line",
        "template_id",
        string="Sunday Stops",
        domain=[("weekday", "=", "sunday")],
    )
    notes = fields.Text(string="Planning Notes")

    off_day = fields.Selection(related="company_id.route_weekly_off_day", string="Weekly Off Day", readonly=True)
    line_count = fields.Integer(string="Template Stops", compute="_compute_template_stats")
    off_day_stop_count = fields.Integer(string="Off-Day Stops", compute="_compute_template_stats")
    city_summary = fields.Char(string="Cities", compute="_compute_template_stats")
    area_summary = fields.Char(string="Areas", compute="_compute_template_stats")
    outlet_summary = fields.Char(string="Outlets", compute="_compute_template_stats")
    schedule_count = fields.Integer(string="Generated Weeks", compute="_compute_template_stats")
    search_city_ids = fields.Many2many(
        "route.city",
        string="Search Cities",
        compute="_compute_search_relations",
        store=True,
    )
    search_area_ids = fields.Many2many(
        "route.area",
        string="Search Areas",
        compute="_compute_search_relations",
        store=True,
    )
    search_outlet_ids = fields.Many2many(
        "route.outlet",
        string="Search Outlets",
        compute="_compute_search_relations",
        store=True,
    )

    @api.depends(
        "line_ids",
        "line_ids.weekday",
        "line_ids.city_id",
        "line_ids.area_id",
        "line_ids.outlet_id",
        "company_id.route_weekly_off_day",
    )
    def _compute_template_stats(self):
        Schedule = self.env["route.weekly.schedule"]
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.off_day_stop_count = len(rec.line_ids.filtered(lambda line: line.weekday == rec.off_day)) if rec.off_day else 0
            city_names = list(dict.fromkeys(rec.line_ids.mapped("city_id.name")))
            area_names = list(dict.fromkeys(rec.line_ids.mapped("area_id.name")))
            outlet_names = list(dict.fromkeys(rec.line_ids.mapped("outlet_id.name")))
            rec.city_summary = rec._format_summary(city_names, max_items=2)
            rec.area_summary = rec._format_summary(area_names, max_items=2)
            rec.outlet_summary = rec._format_summary(outlet_names, max_items=3)
            rec.schedule_count = Schedule.search_count([
                ("template_id", "=", rec.id),
                ("state", "!=", "cancelled"),
            ])

    @api.depends("line_ids.city_id", "line_ids.area_id", "line_ids.outlet_id")
    def _compute_search_relations(self):
        for rec in self:
            city_ids = rec.line_ids.mapped("city_id").ids
            area_ids = rec.line_ids.mapped("area_id").ids
            outlet_ids = rec.line_ids.mapped("outlet_id").ids
            rec.search_city_ids = rec.env["route.city"].browse(city_ids)
            rec.search_area_ids = rec.env["route.area"].browse(area_ids)
            rec.search_outlet_ids = rec.env["route.outlet"].browse(outlet_ids)

    def _format_summary(self, names, max_items=2):
        names = [name for name in names if name]
        if not names:
            return ""
        if len(names) <= max_items:
            return ", ".join(names)
        return "%s ..." % ", ".join(names[:max_items])

    def _sanitize_line_dicts(self, line_dicts):
        sanitized = []
        seen = set()
        next_sequence = 10
        for line_dict in line_dicts:
            weekday = line_dict.get("weekday") or "monday"
            outlet_id = line_dict.get("outlet_id")
            if not outlet_id:
                continue
            key = (weekday, outlet_id)
            if key in seen:
                continue
            seen.add(key)
            values = dict(line_dict)
            values["weekday"] = weekday
            values["sequence"] = values.get("sequence") or next_sequence
            sanitized.append(values)
            next_sequence = max(next_sequence + 10, values["sequence"] + 10)
        return sanitized


    def _cleanup_duplicate_lines(self):
        for rec in self:
            seen = set()
            duplicate_lines = rec.env["route.schedule.template.line"]
            for line in rec.line_ids.sorted(key=lambda item: (item.weekday or "", item.sequence, item.id)):
                key = (line.weekday, line.outlet_id.id)
                if key in seen:
                    duplicate_lines |= line
                else:
                    seen.add(key)
            if duplicate_lines:
                duplicate_lines.unlink()

    def _get_off_day_lines(self):
        self.ensure_one()
        if not self.off_day:
            return self.env["route.schedule.template.line"]
        return self.line_ids.filtered(lambda line: line.weekday == self.off_day)

    def _prepare_schedule_line_commands(self):
        self.ensure_one()
        line_dicts = []
        for line in self.line_ids.sorted(key=lambda item: (item.weekday or "", item.sequence, item.id)):
            line_dicts.append({
                "sequence": line.sequence,
                "weekday": line.weekday,
                "city_id": line.city_id.id,
                "area_id": line.area_id.id,
                "outlet_id": line.outlet_id.id,
                "note": line.note,
            })
        return [fields.Command.create(values) for values in self._sanitize_line_dicts(line_dicts)]

    def _get_default_week_start(self, offset_weeks=0):
        self.ensure_one()
        company = self.company_id or self.env.company
        reference_date = fields.Date.context_today(self)
        week_start_date = compute_week_start_date(
            reference_date,
            week_start_day=company.route_week_start_day or "monday",
        )
        if not week_start_date:
            return False
        if offset_weeks:
            week_start_date = week_start_date + timedelta(days=offset_weeks * 7)
        return week_start_date

    def _get_existing_schedule(self, week_start_date):
        self.ensure_one()
        return self.env["route.weekly.schedule"].search([
            ("template_id", "=", self.id),
            ("week_start_date", "=", week_start_date),
            ("user_id", "=", self.user_id.id),
            ("vehicle_id", "=", self.vehicle_id.id),
            ("state", "!=", "cancelled"),
        ], limit=1)

    def _create_or_open_schedule(self, week_start_date):
        self.ensure_one()
        self._cleanup_duplicate_lines()
        existing_schedule = self._get_existing_schedule(week_start_date)
        if existing_schedule:
            existing_schedule._cleanup_duplicate_lines()
            return existing_schedule.action_open_form()

        schedule = self.env["route.weekly.schedule"].create({
            "template_id": self.id,
            "week_start_date": week_start_date,
            "user_id": self.user_id.id,
            "vehicle_id": self.vehicle_id.id,
            "source_warehouse_id": self.source_warehouse_id.id,
            "notes": self.notes,
            "line_ids": self._prepare_schedule_line_commands(),
        })
        return schedule.action_open_form()

    def action_create_current_week_schedule(self):
        self.ensure_one()
        return self._create_or_open_schedule(self._get_default_week_start(offset_weeks=0))

    def action_create_next_week_schedule(self):
        self.ensure_one()
        return self._create_or_open_schedule(self._get_default_week_start(offset_weeks=1))

    def action_view_weekly_schedules(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_weekly_schedule").read()[0]
        action["domain"] = [("template_id", "=", self.id)]
        action["context"] = {
            **self.env.context,
            "default_template_id": self.id,
            "default_user_id": self.user_id.id,
            "default_vehicle_id": self.vehicle_id.id,
            "default_source_warehouse_id": self.source_warehouse_id.id,
        }
        return action


class RouteScheduleTemplateLine(models.Model):
    _name = "route.schedule.template.line"
    _description = "Route Schedule Template Line"
    _order = "weekday, sequence, id"

    sequence = fields.Integer(string="Sequence", default=10)
    template_id = fields.Many2one(
        "route.schedule.template",
        string="Template",
        required=True,
        ondelete="cascade",
    )
    weekday = fields.Selection(
        WEEKDAY_SELECTION,
        string="Weekday",
        required=True,
        default="monday",
    )
    weekday_label = fields.Char(string="Weekday Label", compute="_compute_weekday_label")
    is_off_day = fields.Boolean(string="Weekly Off Day", compute="_compute_is_off_day")
    city_id = fields.Many2one(
        "route.city",
        string="City",
        required=True,
        ondelete="restrict",
    )
    area_id = fields.Many2one(
        "route.area",
        string="Area",
        required=True,
        ondelete="restrict",
        domain="[('city_id', '=', city_id)]",
    )
    outlet_id = fields.Many2one(
        "route.outlet",
        string="Outlet",
        required=True,
        ondelete="restrict",
        domain="[('area_id', '=', area_id)]",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        related="outlet_id.partner_id",
        store=True,
        readonly=True,
    )
    visit_mode = fields.Selection(
        related="outlet_id.outlet_operation_mode",
        string="Visit Type",
        readonly=True,
        store=False,
    )
    note = fields.Text(string="Line Note")
    same_day_used_outlet_ids = fields.Many2many(
        "route.outlet",
        string="Same-Day Used Outlets",
        compute="_compute_same_day_outlet_helpers",
    )
    available_outlet_ids = fields.Many2many(
        "route.outlet",
        string="Available Outlets",
        compute="_compute_same_day_outlet_helpers",
    )

    @api.depends("weekday")
    def _compute_weekday_label(self):
        for rec in self:
            rec.weekday_label = WEEKDAY_LABELS.get(rec.weekday or "", "")

    @api.depends("weekday", "template_id.company_id.route_weekly_off_day")
    def _compute_is_off_day(self):
        for rec in self:
            rec.is_off_day = bool(
                rec.weekday
                and rec.template_id.company_id.route_weekly_off_day
                and rec.weekday == rec.template_id.company_id.route_weekly_off_day
            )

    def _get_effective_weekday(self):
        self.ensure_one()
        return self.weekday or self.env.context.get("default_weekday") or "monday"

    def _get_parent_lines(self):
        self.ensure_one()
        return self.template_id.line_ids

    def _is_current_line(self, line):
        self.ensure_one()
        line.ensure_one()
        if line == self:
            return True
        self_real_id = self._origin.id or (self.id if isinstance(self.id, int) else False)
        line_real_id = line._origin.id or (line.id if isinstance(line.id, int) else False)
        if self_real_id and line_real_id and self_real_id == line_real_id:
            return True
        return False

    def _get_same_day_sibling_lines(self):
        self.ensure_one()
        weekday = self._get_effective_weekday()
        sibling_lines = self.env["route.schedule.template.line"]

        for line in self._get_parent_lines():
            if not line.outlet_id:
                continue
            if (line.weekday or "monday") != weekday:
                continue
            if self._is_current_line(line):
                continue
            sibling_lines |= line

        if not sibling_lines and self.template_id and self.template_id.id:
            real_id = self._origin.id or (self.id if isinstance(self.id, int) else False)
            domain = [
                ("template_id", "=", self.template_id.id),
                ("weekday", "=", weekday),
                ("outlet_id", "!=", False),
            ]
            if real_id:
                domain.append(("id", "!=", real_id))
            sibling_lines = self.search(domain)
        return sibling_lines

    def _get_duplicate_line(self):
        self.ensure_one()
        if not self.template_id or not self.outlet_id:
            return self.env[self._name]

        weekday = self._get_effective_weekday()
        duplicate_line = self._get_same_day_sibling_lines().filtered(
            lambda line: line.outlet_id == self.outlet_id and (line.weekday or "monday") == weekday
        )[:1]
        if duplicate_line:
            return duplicate_line

        if not self.id:
            return self.env[self._name]

        return self.search([
            ("template_id", "=", self.template_id.id),
            ("weekday", "=", weekday),
            ("outlet_id", "=", self.outlet_id.id),
            ("id", "!=", self.id),
        ], limit=1)

    def _get_available_outlet_ids(self):
        self.ensure_one()
        Outlet = self.env["route.outlet"]
        if not self.area_id:
            return []
        allowed_outlets = Outlet.search([("area_id", "=", self.area_id.id)])
        used_outlets = self._get_same_day_sibling_lines().mapped("outlet_id")
        available_outlets = allowed_outlets - used_outlets
        if self.outlet_id and self.outlet_id.area_id == self.area_id:
            available_outlets |= self.outlet_id
        return available_outlets.ids

    def _get_available_outlet_domain(self):
        self.ensure_one()
        available_ids = self._get_available_outlet_ids()
        return [("id", "in", available_ids)] if available_ids else [("id", "=", 0)]

    def _get_dynamic_domains(self):
        self.ensure_one()
        area_domain = [("city_id", "=", self.city_id.id)] if self.city_id else []
        return {
            "area_id": area_domain,
            "outlet_id": self._get_available_outlet_domain(),
        }

    @api.depends(
        "weekday",
        "city_id",
        "area_id",
        "template_id.line_ids.weekday",
        "template_id.line_ids.outlet_id",
        "template_id.line_ids.area_id",
        "template_id.line_ids.city_id",
    )
    def _compute_same_day_outlet_helpers(self):
        Outlet = self.env["route.outlet"]
        for rec in self:
            used_outlet_ids = rec._get_same_day_sibling_lines().mapped("outlet_id").ids
            rec.same_day_used_outlet_ids = Outlet.browse(used_outlet_ids)
            rec.available_outlet_ids = Outlet.browse(rec._get_available_outlet_ids())

    @api.model_create_multi
    def create(self, vals_list):
        default_weekday = self.env.context.get("default_weekday")
        for vals in vals_list:
            if default_weekday and not vals.get("weekday"):
                vals["weekday"] = default_weekday
            outlet_id = vals.get("outlet_id")
            if outlet_id and not vals.get("area_id"):
                outlet = self.env["route.outlet"].browse(outlet_id)
                vals["area_id"] = outlet.area_id.id
                vals["city_id"] = outlet.area_id.city_id.id
            area_id = vals.get("area_id")
            if area_id and not vals.get("city_id"):
                vals["city_id"] = self.env["route.area"].browse(area_id).city_id.id
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        default_weekday = self.env.context.get("default_weekday")
        if default_weekday and "weekday" not in vals:
            vals["weekday"] = default_weekday
        if vals.get("outlet_id") and not vals.get("area_id"):
            outlet = self.env["route.outlet"].browse(vals["outlet_id"])
            vals["area_id"] = outlet.area_id.id
            vals["city_id"] = outlet.area_id.city_id.id
        elif vals.get("area_id") and not vals.get("city_id"):
            vals["city_id"] = self.env["route.area"].browse(vals["area_id"]).city_id.id
        return super().write(vals)

    @api.onchange("city_id", "weekday")
    def _onchange_city_id(self):
        self.ensure_one()
        if self.area_id and self.area_id.city_id != self.city_id:
            self.area_id = False
        if self.outlet_id and self.outlet_id.area_id.city_id != self.city_id:
            self.outlet_id = False
        return {"domain": self._get_dynamic_domains()}

    @api.onchange("area_id", "weekday")
    def _onchange_area_id(self):
        self.ensure_one()
        if self.area_id and self.area_id.city_id != self.city_id:
            self.city_id = self.area_id.city_id
        if self.outlet_id and self.outlet_id.area_id != self.area_id:
            self.outlet_id = False
        return {"domain": self._get_dynamic_domains()}

    @api.onchange("weekday")
    def _onchange_weekday_warning(self):
        self.ensure_one()
        off_day = self.template_id.company_id.route_weekly_off_day
        response = {"domain": self._get_dynamic_domains()}
        if self._get_effective_weekday() and off_day and self._get_effective_weekday() == off_day:
            response["warning"] = {
                "title": _("Weekly Off Day"),
                "message": _(
                    "This stop is scheduled on the configured weekly off day. It will be highlighted for supervisor review and skipped when daily plans are generated."
                ),
            }
        return response

    @api.onchange("outlet_id")
    def _onchange_outlet_id(self):
        self.ensure_one()
        response = {"domain": self._get_dynamic_domains()}
        if not self.outlet_id:
            return response

        selected_outlet = self.outlet_id
        self.area_id = selected_outlet.area_id
        self.city_id = selected_outlet.area_id.city_id
        duplicate_line = self._get_duplicate_line()
        if duplicate_line:
            self.outlet_id = False
            response["domain"] = self._get_dynamic_domains()
            response["warning"] = {
                "title": _("Duplicate Outlet"),
                "message": _(
                    "Outlet %(outlet)s is already added on %(day)s in this weekly visit template. Choose another outlet for that day."
                ) % {
                    "outlet": selected_outlet.display_name or selected_outlet.name,
                    "day": WEEKDAY_LABELS.get(self._get_effective_weekday() or "", self._get_effective_weekday() or ""),
                },
            }
            return response

        response["domain"] = self._get_dynamic_domains()
        return response

    @api.constrains("city_id", "area_id", "outlet_id")
    def _check_area_matches_outlet(self):
        for rec in self:
            if rec.city_id and rec.area_id and rec.area_id.city_id != rec.city_id:
                raise ValidationError(_("The selected area does not belong to the selected city."))
            if rec.area_id and rec.outlet_id and rec.outlet_id.area_id != rec.area_id:
                raise ValidationError(_("The selected outlet does not belong to the selected area."))
            if rec.city_id and rec.outlet_id and rec.outlet_id.area_id.city_id != rec.city_id:
                raise ValidationError(_("The selected outlet does not belong to the selected city."))

    @api.constrains("template_id", "weekday", "outlet_id")
    def _check_duplicate_outlet_per_day(self):
        for rec in self.filtered(lambda line: line.template_id and line.outlet_id):
            duplicate = self.search([
                ("id", "!=", rec.id),
                ("template_id", "=", rec.template_id.id),
                ("weekday", "=", rec.weekday or "monday"),
                ("outlet_id", "=", rec.outlet_id.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    "Outlet %(outlet)s is already added on %(day)s in this weekly visit template. Choose another outlet or keep only one line for that day."
                ) % {
                    "outlet": rec.outlet_id.display_name or rec.outlet_id.name,
                    "day": WEEKDAY_LABELS.get(rec.weekday or "", rec.weekday or ""),
                })

