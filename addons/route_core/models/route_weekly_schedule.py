from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .route_schedule_common import (
    WEEKDAY_SELECTION,
    WEEKDAY_LABELS,
    compute_weekday_date,
)


class RouteWeeklySchedule(models.Model):
    _name = "route.weekly.schedule"
    _description = "Weekly Route Schedule"
    _order = "week_start_date desc, id desc"

    name = fields.Char(string="Schedule Reference", required=True, copy=False, readonly=True, default="New")
    week_start_date = fields.Date(string="Week Start", required=True, default=fields.Date.context_today)
    week_end_date = fields.Date(string="Week End", compute="_compute_week_range", store=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        readonly=True,
    )
    template_id = fields.Many2one(
        "route.schedule.template",
        string="Route Template",
        ondelete="set null",
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
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("plans_generated", "Daily Plans Generated"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
    )
    notes = fields.Text(string="Planning Notes")
    line_ids = fields.One2many(
        "route.weekly.schedule.line",
        "schedule_id",
        string="Scheduled Stops",
    )
    monday_line_ids = fields.One2many("route.weekly.schedule.line", "schedule_id", string="Monday Stops")
    tuesday_line_ids = fields.One2many("route.weekly.schedule.line", "schedule_id", string="Tuesday Stops")
    wednesday_line_ids = fields.One2many("route.weekly.schedule.line", "schedule_id", string="Wednesday Stops")
    thursday_line_ids = fields.One2many("route.weekly.schedule.line", "schedule_id", string="Thursday Stops")
    friday_line_ids = fields.One2many("route.weekly.schedule.line", "schedule_id", string="Friday Stops")
    saturday_line_ids = fields.One2many("route.weekly.schedule.line", "schedule_id", string="Saturday Stops")
    sunday_line_ids = fields.One2many("route.weekly.schedule.line", "schedule_id", string="Sunday Stops")
    route_plan_ids = fields.Many2many(
        "route.plan",
        string="Generated Daily Plans",
        compute="_compute_schedule_stats",
    )
    line_count = fields.Integer(string="Scheduled Stops", compute="_compute_schedule_stats")
    off_day_stop_count = fields.Integer(string="Off-Day Stops", compute="_compute_schedule_stats")
    generated_plan_count = fields.Integer(string="Generated Plans", compute="_compute_schedule_stats")
    city_summary = fields.Char(string="Cities", compute="_compute_schedule_stats")
    area_summary = fields.Char(string="Areas", compute="_compute_schedule_stats")
    outlet_summary = fields.Char(string="Outlets", compute="_compute_schedule_stats")
    off_day = fields.Selection(related="company_id.route_weekly_off_day", string="Weekly Off Day", readonly=True)
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

    @api.depends("week_start_date")
    def _compute_week_range(self):
        for rec in self:
            if rec.week_start_date:
                rec.week_end_date = fields.Date.add(rec.week_start_date, days=6)
            else:
                rec.week_end_date = False

    @api.depends("line_ids", "line_ids.weekday", "line_ids.area_id", "line_ids.outlet_id", "line_ids.generated_plan_id", "company_id.route_weekly_off_day")
    def _compute_schedule_stats(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.off_day_stop_count = len(rec.line_ids.filtered(lambda line: line.weekday == rec.off_day)) if rec.off_day else 0
            rec.route_plan_ids = rec.line_ids.mapped("generated_plan_id")
            rec.generated_plan_count = len(rec.route_plan_ids)
            city_names = list(dict.fromkeys(rec.line_ids.mapped("city_id.name")))
            area_names = list(dict.fromkeys(rec.line_ids.mapped("area_id.name")))
            outlet_names = list(dict.fromkeys(rec.line_ids.mapped("outlet_id.name")))
            rec.city_summary = rec._format_summary(city_names, max_items=2)
            rec.area_summary = rec._format_summary(area_names, max_items=2)
            rec.outlet_summary = rec._format_summary(outlet_names, max_items=3)

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

    @api.model_create_multi
    def create(self, vals_list):
        schedules = super().create(vals_list)
        for schedule, vals in zip(schedules, vals_list):
            if vals.get("template_id") and not vals.get("line_ids"):
                schedule._load_template_lines()
            if not vals.get("name") or vals.get("name") == "New":
                schedule.name = schedule._build_schedule_name()
        return schedules

    def write(self, vals):
        result = super().write(vals)
        if vals.get("template_id") and not vals.get("line_ids"):
            for rec in self:
                if rec.template_id and not rec.line_ids:
                    rec._load_template_lines()
        return result

    def _build_schedule_name(self):
        self.ensure_one()
        date_token = fields.Date.to_string(self.week_start_date or fields.Date.context_today(self)).replace("-", "")
        return "WS/%s/%04d" % (date_token, self.id)

    def _load_template_lines(self):
        self.ensure_one()
        if not self.template_id:
            return
        commands = [fields.Command.clear()]
        for line in self.template_id.line_ids.sorted(key=lambda item: (item.sequence, item.id)):
            commands.append(fields.Command.create({
                "sequence": line.sequence,
                "weekday": line.weekday,
                "area_id": line.area_id.id,
                "outlet_id": line.outlet_id.id,
                "note": line.note,
            }))
        self.line_ids = commands
        if not self.source_warehouse_id and self.template_id.source_warehouse_id:
            self.source_warehouse_id = self.template_id.source_warehouse_id
        if not self.user_id and self.template_id.user_id:
            self.user_id = self.template_id.user_id
        if not self.vehicle_id and self.template_id.vehicle_id:
            self.vehicle_id = self.template_id.vehicle_id
        if not self.notes and self.template_id.notes:
            self.notes = self.template_id.notes

    @api.onchange("template_id")
    def _onchange_template_id(self):
        for rec in self:
            if rec.template_id:
                rec._load_template_lines()

    def _get_daily_plan_for_date(self, visit_date):
        self.ensure_one()
        return self.env["route.plan"].search([
            ("date", "=", visit_date),
            ("user_id", "=", self.user_id.id),
            ("vehicle_id", "=", self.vehicle_id.id),
            ("state", "!=", "cancel"),
        ], limit=1)

    def _prepare_route_plan_vals(self, visit_date, schedule_lines):
        self.ensure_one()
        area_ids = schedule_lines.mapped("area_id").ids
        plan_area_id = area_ids[0] if len(area_ids) == 1 else False
        return {
            "date": visit_date,
            "user_id": self.user_id.id,
            "vehicle_id": self.vehicle_id.id,
            "company_id": self.company_id.id,
            "source_warehouse_id": self.source_warehouse_id.id or False,
            "area_id": plan_area_id,
            "notes": _("Generated from weekly route schedule %s.") % (self.name,),
            "weekly_schedule_id": self.id,
        }

    def action_generate_daily_plans(self):
        Plan = self.env["route.plan"]
        PlanLine = self.env["route.plan.line"]

        for rec in self:
            if not rec.line_ids:
                raise UserError(_("Please add scheduled stops before generating daily plans."))

            processable_lines = rec.line_ids.filtered(lambda line: line.weekday != rec.off_day) if rec.off_day else rec.line_ids
            if not processable_lines:
                raise UserError(_("All scheduled stops fall on the configured weekly off day. Move them to working days before generating daily plans."))

            weekday_codes = sorted({line.weekday for line in rec.line_ids if line.weekday})
            for weekday_code in weekday_codes:
                if weekday_code == rec.off_day:
                    continue
                day_lines = rec.line_ids.filtered(lambda line: line.weekday == weekday_code)
                if not day_lines:
                    continue

                visit_date = compute_weekday_date(
                    rec.week_start_date,
                    weekday_code,
                    week_start_day=rec.company_id.route_week_start_day or "monday",
                )
                if not visit_date:
                    continue

                plan = day_lines[:1].generated_plan_id.filtered(lambda item: item.state != "cancel")
                if not plan:
                    plan = rec._get_daily_plan_for_date(visit_date)

                if plan and plan.planning_finalized:
                    raise UserError(
                        _(
                            "Daily plan %(plan)s for %(date)s is already finalized. "
                            "Please reopen the plan first before syncing weekly schedule changes."
                        )
                        % {
                            "plan": plan.display_name or plan.name,
                            "date": fields.Date.to_string(visit_date),
                        }
                    )

                if not plan:
                    plan = Plan.create(rec._prepare_route_plan_vals(visit_date, day_lines))
                else:
                    update_vals = {}
                    if not plan.weekly_schedule_id:
                        update_vals["weekly_schedule_id"] = rec.id
                    if not plan.source_warehouse_id and rec.source_warehouse_id:
                        update_vals["source_warehouse_id"] = rec.source_warehouse_id.id
                    if not plan.area_id:
                        area_ids = day_lines.mapped("area_id").ids
                        if len(area_ids) == 1:
                            update_vals["area_id"] = area_ids[0]
                    if update_vals:
                        plan.with_context(route_plan_skip_locked_check=True).write(update_vals)

                next_sequence = max(plan.line_ids.mapped("sequence") or [0])
                existing_by_outlet = {
                    line.outlet_id.id: line
                    for line in plan.line_ids.filtered("outlet_id")
                }
                for schedule_line in day_lines.sorted(key=lambda line: (line.sequence, line.id)):
                    plan_line = existing_by_outlet.get(schedule_line.outlet_id.id)
                    if not plan_line:
                        next_sequence += 10
                        plan_line = PlanLine.create({
                            "plan_id": plan.id,
                            "sequence": next_sequence,
                            "area_id": schedule_line.area_id.id,
                            "outlet_id": schedule_line.outlet_id.id,
                            "note": schedule_line.note,
                        })
                        existing_by_outlet[schedule_line.outlet_id.id] = plan_line
                    schedule_line.write({
                        "generated_plan_id": plan.id,
                        "generated_plan_line_id": plan_line.id,
                    })

            rec.state = "plans_generated"

        return self.action_open_daily_plans()

    def action_copy_to_next_week(self):
        self.ensure_one()
        next_week_start = fields.Date.add(self.week_start_date, days=7)
        existing_schedule = self.search([
            ("template_id", "=", self.template_id.id),
            ("week_start_date", "=", next_week_start),
            ("user_id", "=", self.user_id.id),
            ("vehicle_id", "=", self.vehicle_id.id),
            ("state", "!=", "cancelled"),
        ], limit=1)
        if existing_schedule:
            return existing_schedule.action_open_form()

        new_schedule = self.copy({
            "name": "New",
            "week_start_date": next_week_start,
            "state": "draft",
            "line_ids": [
                fields.Command.clear(),
                *[
                    fields.Command.create({
                        "sequence": line.sequence,
                        "weekday": line.weekday,
                        "city_id": line.city_id.id,
                        "area_id": line.area_id.id,
                        "outlet_id": line.outlet_id.id,
                        "note": line.note,
                    })
                    for line in self.line_ids.sorted(key=lambda item: (item.sequence, item.id))
                ],
            ],
        })
        new_schedule.name = new_schedule._build_schedule_name()
        return new_schedule.action_open_form()

    def action_open_daily_plans(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_plan").read()[0]
        plan_ids = self.line_ids.mapped("generated_plan_id").ids
        action["domain"] = [("id", "in", plan_ids)] if plan_ids else [("id", "=", 0)]
        return action

    def action_open_template(self):
        self.ensure_one()
        if not self.template_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Weekly Route Template"),
            "res_model": "route.schedule.template",
            "res_id": self.template_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_form(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Weekly Route Schedule"),
            "res_model": "route.weekly.schedule",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_cancel_schedule(self):
        self.write({"state": "cancelled"})
        return True

    def action_reset_to_draft(self):
        self.write({"state": "draft"})
        return True


class RouteWeeklyScheduleLine(models.Model):
    _name = "route.weekly.schedule.line"
    _description = "Weekly Route Schedule Line"
    _order = "weekday, sequence, id"

    sequence = fields.Integer(string="Sequence", default=10)
    schedule_id = fields.Many2one(
        "route.weekly.schedule",
        string="Weekly Schedule",
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
    visit_date = fields.Date(string="Visit Date", compute="_compute_visit_date")
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
    generated_plan_id = fields.Many2one(
        "route.plan",
        string="Generated Daily Plan",
        readonly=True,
        copy=False,
        ondelete="set null",
    )
    generated_plan_line_id = fields.Many2one(
        "route.plan.line",
        string="Generated Daily Plan Line",
        readonly=True,
        copy=False,
        ondelete="set null",
    )

    _sql_constraints = [
        (
            "route_weekly_schedule_line_unique_outlet_day",
            "unique(schedule_id, weekday, outlet_id)",
            "You cannot schedule the same outlet more than once on the same weekday in one weekly schedule.",
        )
    ]

    @api.depends("weekday")
    def _compute_weekday_label(self):
        for rec in self:
            rec.weekday_label = WEEKDAY_LABELS.get(rec.weekday or "", "")

    @api.depends("weekday", "schedule_id.company_id.route_weekly_off_day")
    def _compute_is_off_day(self):
        for rec in self:
            rec.is_off_day = bool(rec.weekday and rec.schedule_id.company_id.route_weekly_off_day and rec.weekday == rec.schedule_id.company_id.route_weekly_off_day)

    @api.depends("schedule_id.week_start_date", "weekday", "schedule_id.company_id.route_week_start_day")
    def _compute_visit_date(self):
        for rec in self:
            rec.visit_date = compute_weekday_date(
                rec.schedule_id.week_start_date,
                rec.weekday,
                week_start_day=rec.schedule_id.company_id.route_week_start_day or "monday",
            )

    @api.onchange("weekday")
    def _onchange_weekday_warning(self):
        for rec in self:
            off_day = rec.schedule_id.company_id.route_weekly_off_day
            if rec.weekday and off_day and rec.weekday == off_day:
                return {
                    "warning": {
                        "title": _("Weekly Off Day"),
                        "message": _("This stop is scheduled on the configured weekly off day. It will remain visible for review but will be skipped during daily plan generation."),
                    }
                }

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
