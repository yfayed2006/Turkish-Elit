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
    monday_line_ids = fields.One2many("route.schedule.template.line", "template_id", string="Monday Stops")
    tuesday_line_ids = fields.One2many("route.schedule.template.line", "template_id", string="Tuesday Stops")
    wednesday_line_ids = fields.One2many("route.schedule.template.line", "template_id", string="Wednesday Stops")
    thursday_line_ids = fields.One2many("route.schedule.template.line", "template_id", string="Thursday Stops")
    friday_line_ids = fields.One2many("route.schedule.template.line", "template_id", string="Friday Stops")
    saturday_line_ids = fields.One2many("route.schedule.template.line", "template_id", string="Saturday Stops")
    sunday_line_ids = fields.One2many("route.schedule.template.line", "template_id", string="Sunday Stops")
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

    @api.depends("line_ids", "line_ids.weekday", "line_ids.area_id", "line_ids.outlet_id", "company_id.route_weekly_off_day")
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

    @api.depends("line_ids.area_id", "line_ids.outlet_id")
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

    def _get_off_day_lines(self):
        self.ensure_one()
        if not self.off_day:
            return self.env["route.schedule.template.line"]
        return self.line_ids.filtered(lambda line: line.weekday == self.off_day)

    def _prepare_schedule_line_commands(self):
        commands = []
        for line in self.line_ids.sorted(key=lambda item: (item.sequence, item.id)):
            commands.append(fields.Command.create({
                "sequence": line.sequence,
                "weekday": line.weekday,
                "city_id": line.city_id.id,
                "area_id": line.area_id.id,
                "outlet_id": line.outlet_id.id,
                "note": line.note,
            }))
        return commands

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
        existing_schedule = self._get_existing_schedule(week_start_date)
        if existing_schedule:
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

    _sql_constraints = [
        (
            "route_schedule_template_line_unique_outlet_day",
            "unique(template_id, weekday, outlet_id)",
            "You cannot schedule the same outlet more than once on the same weekday in one template.",
        )
    ]

    @api.depends("weekday")
    def _compute_weekday_label(self):
        for rec in self:
            rec.weekday_label = WEEKDAY_LABELS.get(rec.weekday or "", "")

    @api.depends("weekday", "template_id.company_id.route_weekly_off_day")
    def _compute_is_off_day(self):
        for rec in self:
            rec.is_off_day = bool(rec.weekday and rec.template_id.company_id.route_weekly_off_day and rec.weekday == rec.template_id.company_id.route_weekly_off_day)

    @api.onchange("city_id")
    def _onchange_city_id(self):
        for rec in self:
            if rec.area_id and rec.area_id.city_id != rec.city_id:
                rec.area_id = False
            if rec.outlet_id and rec.outlet_id.area_id.city_id != rec.city_id:
                rec.outlet_id = False
            return {
                "domain": {
                    "area_id": [("city_id", "=", rec.city_id.id)] if rec.city_id else [],
                    "outlet_id": [("area_id.city_id", "=", rec.city_id.id)] if rec.city_id else [],
                }
            }

    @api.onchange("area_id")
    def _onchange_area_id(self):
        for rec in self:
            if rec.area_id and rec.area_id.city_id != rec.city_id:
                rec.city_id = rec.area_id.city_id
            if rec.outlet_id and rec.outlet_id.area_id != rec.area_id:
                rec.outlet_id = False
            return {
                "domain": {
                    "outlet_id": [("area_id", "=", rec.area_id.id)] if rec.area_id else ([('area_id.city_id', '=', rec.city_id.id)] if rec.city_id else []),
                }
            }

    @api.onchange("weekday")
    def _onchange_weekday_warning(self):
        for rec in self:
            off_day = rec.template_id.company_id.route_weekly_off_day
            if rec.weekday and off_day and rec.weekday == off_day:
                return {
                    "warning": {
                        "title": _("Weekly Off Day"),
                        "message": _("This stop is scheduled on the configured weekly off day. It will be highlighted for supervisor review and skipped when daily plans are generated."),
                    }
                }

    @api.onchange("outlet_id")
    def _onchange_outlet_id(self):
        for rec in self:
            if rec.outlet_id:
                rec.area_id = rec.outlet_id.area_id
                rec.city_id = rec.outlet_id.area_id.city_id

    @api.constrains("city_id", "area_id", "outlet_id")
    def _check_area_matches_outlet(self):
        for rec in self:
            if rec.city_id and rec.area_id and rec.area_id.city_id != rec.city_id:
                raise ValidationError(
                    _("The selected area does not belong to the selected city.")
                )
            if rec.area_id and rec.outlet_id and rec.outlet_id.area_id != rec.area_id:
                raise ValidationError(
                    _("The selected outlet does not belong to the selected area.")
                )
            if rec.city_id and rec.outlet_id and rec.outlet_id.area_id.city_id != rec.city_id:
                raise ValidationError(
                    _("The selected outlet does not belong to the selected city.")
                )

