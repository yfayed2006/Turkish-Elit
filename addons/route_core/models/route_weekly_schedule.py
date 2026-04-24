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
        string="Weekly Visit Template",
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
    display_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("plans_generated", "Plans Ready"),
            ("in_progress", "Execution"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Workflow Status",
        compute="_compute_display_state",
        store=True,
    )
    line_ids = fields.One2many(
        "route.weekly.schedule.line",
        "schedule_id",
        string="Scheduled Stops",
    )
    monday_line_ids = fields.One2many(
        "route.weekly.schedule.line",
        "schedule_id",
        string="Monday Stops",
        domain=[("weekday", "=", "monday")],
    )
    tuesday_line_ids = fields.One2many(
        "route.weekly.schedule.line",
        "schedule_id",
        string="Tuesday Stops",
        domain=[("weekday", "=", "tuesday")],
    )
    wednesday_line_ids = fields.One2many(
        "route.weekly.schedule.line",
        "schedule_id",
        string="Wednesday Stops",
        domain=[("weekday", "=", "wednesday")],
    )
    thursday_line_ids = fields.One2many(
        "route.weekly.schedule.line",
        "schedule_id",
        string="Thursday Stops",
        domain=[("weekday", "=", "thursday")],
    )
    friday_line_ids = fields.One2many(
        "route.weekly.schedule.line",
        "schedule_id",
        string="Friday Stops",
        domain=[("weekday", "=", "friday")],
    )
    saturday_line_ids = fields.One2many(
        "route.weekly.schedule.line",
        "schedule_id",
        string="Saturday Stops",
        domain=[("weekday", "=", "saturday")],
    )
    sunday_line_ids = fields.One2many(
        "route.weekly.schedule.line",
        "schedule_id",
        string="Sunday Stops",
        domain=[("weekday", "=", "sunday")],
    )
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
    skipped_finalized_plan_count = fields.Integer(string="Finalized Days Skipped", compute="_compute_schedule_stats")
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

    @api.depends(
        "state",
        "line_ids.generated_plan_id",
        "line_ids.generated_plan_id.state",
    )
    def _compute_display_state(self):
        for rec in self:
            if rec.state == "cancelled":
                rec.display_state = "cancelled"
                continue

            linked_plans = rec.line_ids.mapped("generated_plan_id").filtered(
                lambda plan: plan and plan.state != "cancel"
            )
            linked_states = set(linked_plans.mapped("state"))

            if linked_plans and linked_states and linked_states.issubset({"done"}):
                rec.display_state = "done"
            elif "in_progress" in linked_states:
                rec.display_state = "in_progress"
            elif rec.state == "plans_generated":
                rec.display_state = "plans_generated"
            else:
                rec.display_state = "draft"

    @api.depends("week_start_date")
    def _compute_week_range(self):
        for rec in self:
            rec.week_end_date = fields.Date.add(rec.week_start_date, days=6) if rec.week_start_date else False

    @api.depends(
        "line_ids",
        "line_ids.weekday",
        "line_ids.city_id",
        "line_ids.area_id",
        "line_ids.outlet_id",
        "line_ids.generated_plan_id",
        "line_ids.finalized_plan_skip",
        "company_id.route_weekly_off_day",
    )
    def _compute_schedule_stats(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.off_day_stop_count = len(rec.line_ids.filtered(lambda line: line.weekday == rec.off_day)) if rec.off_day else 0
            rec.route_plan_ids = rec.line_ids.mapped("generated_plan_id").filtered(lambda plan: plan.state != "cancel")
            rec.generated_plan_count = len(rec.route_plan_ids)
            rec.skipped_finalized_plan_count = len(set(rec.line_ids.filtered("finalized_plan_skip").mapped("visit_date")))
            city_names = list(dict.fromkeys(rec.line_ids.mapped("city_id.name")))
            area_names = list(dict.fromkeys(rec.line_ids.mapped("area_id.name")))
            outlet_names = list(dict.fromkeys(rec.line_ids.mapped("outlet_id.name")))
            rec.city_summary = rec._format_summary(city_names, max_items=2)
            rec.area_summary = rec._format_summary(area_names, max_items=2)
            rec.outlet_summary = rec._format_summary(outlet_names, max_items=3)

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

    @api.model_create_multi
    def create(self, vals_list):
        cleaned_vals_list = []
        for vals in vals_list:
            cleaned_vals = dict(vals)
            commands = cleaned_vals.get("line_ids") or []
            if commands:
                line_dicts = []
                for command in commands:
                    if not command or command[0] != 0:
                        continue
                    values = dict(command[2] or {})
                    line_dicts.append(values)
                cleaned_vals["line_ids"] = [
                    fields.Command.create(values)
                    for values in self._sanitize_line_dicts(line_dicts)
                ]
            cleaned_vals_list.append(cleaned_vals)

        schedules = super().create(cleaned_vals_list)
        for schedule, vals in zip(schedules, cleaned_vals_list):
            if vals.get("template_id") and not vals.get("line_ids"):
                schedule._load_template_lines()
            if not vals.get("name") or vals.get("name") == "New":
                schedule.name = schedule._build_schedule_name()
        return schedules

    def write(self, vals):
        cleaned_vals = dict(vals)
        commands = cleaned_vals.get("line_ids") or []
        if commands:
            line_dicts = []
            preserved_commands = []
            for command in commands:
                if not command or command[0] != 0:
                    preserved_commands.append(command)
                    continue
                line_dicts.append(dict(command[2] or {}))
            cleaned_vals["line_ids"] = preserved_commands + [
                fields.Command.create(values)
                for values in self._sanitize_line_dicts(line_dicts)
            ]

        allowed_locked_write_fields = {"state"}
        restricted_locked_fields = set(cleaned_vals.keys()) - allowed_locked_write_fields
        if restricted_locked_fields and not self.env.context.get("route_weekly_schedule_skip_lock"):
            for rec in self:
                if rec.state != "draft":
                    raise UserError(
                        _(
                            "This weekly schedule is locked because daily plans have already been generated from it. "
                            "Reset the weekly schedule safely first, or edit the daily route plans directly."
                        )
                    )

        result = super().write(cleaned_vals)
        if cleaned_vals.get("template_id") and not cleaned_vals.get("line_ids"):
            for rec in self:
                if rec.template_id and not rec.line_ids:
                    rec._load_template_lines()
        return result

    def unlink(self):
        if not self.env.context.get("route_weekly_schedule_skip_lock"):
            for rec in self:
                if rec.state != "draft" or rec._get_linked_daily_plans():
                    raise UserError(
                        _(
                            "You cannot delete this weekly schedule after daily plans have been generated from it. "
                            "Cancel or keep the planning record instead."
                        )
                    )
        return super().unlink()

    def _build_schedule_name(self):
        self.ensure_one()
        date_token = fields.Date.to_string(self.week_start_date or fields.Date.context_today(self)).replace("-", "")
        return "WS/%s/%04d" % (date_token, self.id)

    def _load_template_lines(self):
        self.ensure_one()
        if not self.template_id:
            return
        commands = [fields.Command.clear()]
        line_dicts = []
        for line in self.template_id.line_ids.sorted(key=lambda item: (item.weekday or "", item.sequence, item.id)):
            line_dicts.append({
                "sequence": line.sequence,
                "weekday": line.weekday,
                "city_id": line.city_id.id,
                "area_id": line.area_id.id,
                "outlet_id": line.outlet_id.id,
                "note": line.note,
            })
        for values in self._sanitize_line_dicts(line_dicts):
            commands.append(fields.Command.create(values))
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


    def _cleanup_duplicate_lines(self):
        for rec in self:
            seen = set()
            duplicate_lines = rec.env["route.weekly.schedule.line"]
            for line in rec.line_ids.sorted(key=lambda item: (item.weekday or "", item.sequence, item.id)):
                key = (line.weekday, line.outlet_id.id)
                if key in seen:
                    duplicate_lines |= line
                else:
                    seen.add(key)
            if duplicate_lines:
                duplicate_lines.unlink()

    def _ensure_planning_manager(self):
        if self.env.user.has_group("route_core.group_route_supervisor") or self.env.user.has_group("route_core.group_route_management"):
            return
        raise UserError(_("Only route supervisors can manage weekly schedules and planning changes."))

    def _ensure_schedule_draft_editable(self, action_label=None):
        self._ensure_planning_manager()
        for rec in self:
            if rec.state != "draft":
                if action_label:
                    raise UserError(
                        _(
                            "You cannot %(action)s after daily plans have already been generated from this weekly schedule. "
                            "Reset the weekly schedule safely first, or edit the daily route plans directly."
                        )
                        % {"action": action_label}
                    )
                raise UserError(
                    _(
                        "This weekly schedule is locked because daily plans have already been generated from it. "
                        "Reset the weekly schedule safely first, or edit the daily route plans directly."
                    )
                )

    def _get_linked_daily_plans(self):
        self.ensure_one()
        return self.line_ids.mapped("generated_plan_id").filtered(lambda plan: plan and plan.state != "cancel")

    def _get_unsafe_linked_daily_plans(self):
        self.ensure_one()
        return self._get_linked_daily_plans().filtered(
            lambda plan: plan.planning_finalized or plan.visit_count or plan.state in ("in_progress", "done")
        )

    def _format_linked_plan_names(self, plans, max_items=3):
        names = [plan.display_name or plan.name for plan in plans if plan]
        if not names:
            return ""
        if len(names) <= max_items:
            return ", ".join(names)
        return "%s ..." % ", ".join(names[:max_items])

    def _ensure_can_rebuild_generated_plans(self):
        for rec in self:
            unsafe_plans = rec._get_unsafe_linked_daily_plans()
            if unsafe_plans:
                raise UserError(
                    _(
                        "You cannot rebuild this weekly schedule because some generated daily plans are already finalized or execution has already started. "
                        "Please continue with those daily plans directly, or reopen/cancel them first if operationally appropriate.\n\nAffected daily plans: %(plans)s"
                    )
                    % {"plans": rec._format_linked_plan_names(unsafe_plans)}
                )

    def _cancel_safe_linked_daily_plans(self):
        for rec in self:
            linked_plans = rec._get_linked_daily_plans()
            if not linked_plans:
                continue
            linked_plans.with_context(
                route_plan_skip_locked_check=True,
                route_plan_skip_sync=True,
                route_plan_skip_loading_dirty=True,
            ).write({
                "planning_finalized": False,
                "planning_finalized_datetime": False,
                "state": "cancel",
            })

    def _clear_generated_plan_links(self):
        self.mapped("line_ids").with_context(route_weekly_schedule_skip_lock=True).write({
            "generated_plan_id": False,
            "generated_plan_line_id": False,
            "finalized_plan_skip": False,
        })

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
            "notes": _("Generated from weekly visit schedule %s.") % (self.name,),
            "weekly_schedule_id": self.id,
        }

    def _link_existing_plan(self, plan, schedule_lines, skipped=False):
        self.ensure_one()
        existing_plan_lines = {
            line.outlet_id.id: line
            for line in plan.line_ids.filtered("outlet_id")
        }
        for schedule_line in schedule_lines:
            plan_line = existing_plan_lines.get(schedule_line.outlet_id.id)
            schedule_line.write({
                "generated_plan_id": plan.id,
                "generated_plan_line_id": plan_line.id if plan_line else False,
                "finalized_plan_skip": bool(skipped),
            })

    def action_generate_daily_plans(self):
        self._ensure_planning_manager()
        Plan = self.env["route.plan"]
        PlanLine = self.env["route.plan.line"]

        for rec in self:
            rec._ensure_schedule_draft_editable(_("generate daily plans"))
            rec._cleanup_duplicate_lines()
            if not rec.line_ids:
                raise UserError(_("Please add scheduled stops before generating daily plans."))

            processable_lines = rec.line_ids.filtered(lambda line: line.weekday != rec.off_day) if rec.off_day else rec.line_ids
            if not processable_lines:
                raise UserError(_("All scheduled stops fall on the configured weekly off day. Move them to working days before generating daily plans."))

            rec.line_ids.write({"finalized_plan_skip": False})
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
                    rec._link_existing_plan(plan, day_lines, skipped=True)
                    continue

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
                        "finalized_plan_skip": False,
                    })

            rec.state = "plans_generated"

        return self.action_open_daily_plans()

    def action_copy_to_next_week(self):
        self.ensure_one()
        self._ensure_planning_manager()
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

        new_schedule = self.copy({
            "name": "New",
            "week_start_date": next_week_start,
            "state": "draft",
            "line_ids": [
                fields.Command.clear(),
                *[
                    fields.Command.create(values)
                    for values in self._sanitize_line_dicts(line_dicts)
                ],
            ],
        })
        new_schedule.name = new_schedule._build_schedule_name()
        return new_schedule.action_open_form()

    def action_open_daily_plans(self):
        self.ensure_one()
        action_xmlid = "route_core.action_route_plan"
        if self.env.user.has_group("route_core.group_route_salesperson") and not (
            self.env.user.has_group("route_core.group_route_supervisor")
            or self.env.user.has_group("route_core.group_route_management")
        ):
            action_xmlid = "route_core.action_route_plan_salesperson"
        action = self.env.ref(action_xmlid).read()[0]
        plan_ids = self.line_ids.mapped("generated_plan_id").filtered(lambda plan: plan.state != "cancel").ids
        action["domain"] = [("id", "in", plan_ids)] if plan_ids else [("id", "=", 0)]
        return action

    def action_open_template(self):
        self.ensure_one()
        self._ensure_planning_manager()
        if not self.template_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Weekly Visit Template"),
            "res_model": "route.schedule.template",
            "res_id": self.template_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_form(self):
        self.ensure_one()
        self._cleanup_duplicate_lines()
        return {
            "type": "ir.actions.act_window",
            "name": _("Generated Weekly Schedule"),
            "res_model": "route.weekly.schedule",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_cancel_schedule(self):
        self._ensure_planning_manager()
        self._ensure_can_rebuild_generated_plans()
        self._cancel_safe_linked_daily_plans()
        self.with_context(route_weekly_schedule_skip_lock=True).write({"state": "cancelled"})
        return True

    def action_reset_to_draft(self):
        self._ensure_planning_manager()
        self._ensure_can_rebuild_generated_plans()
        self._cancel_safe_linked_daily_plans()
        self._clear_generated_plan_links()
        self.with_context(route_weekly_schedule_skip_lock=True).write({"state": "draft"})
        return True

    def action_open_day_stop_wizard(self):
        self.ensure_one()
        self._ensure_schedule_draft_editable(_("add weekly stops"))
        weekday = self.env.context.get("default_weekday") or self.env.context.get("wizard_weekday") or "monday"
        action = self.env.ref("route_core.action_route_schedule_stop_wizard").read()[0]
        day_lines = self.line_ids.filtered(lambda line: (line.weekday or "monday") == weekday)
        first_line = day_lines[:1]
        action["name"] = _("Create %(day)s Stops") % {
            "day": WEEKDAY_LABELS.get(weekday, weekday.title()),
        }
        action["context"] = {
            **self.env.context,
            "default_schedule_id": self.id,
            "default_weekday": weekday,
            "default_city_id": first_line.city_id.id if first_line else False,
            "default_area_id": first_line.area_id.id if first_line else False,
        }
        return action


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
    execution_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("skipped", "Skipped"),
        ],
        string="Execution Status",
        compute="_compute_execution_status",
    )
    finalized_plan_skip = fields.Boolean(string="Skipped Because Finalized", readonly=True, copy=False)

    @api.depends(
        "generated_plan_id",
        "generated_plan_id.state",
        "generated_plan_line_id",
        "generated_plan_line_id.state",
        "generated_plan_line_id.visit_id",
        "generated_plan_line_id.visit_id.state",
        "generated_plan_line_id.visit_id.visit_process_state",
    )
    def _compute_execution_status(self):
        for rec in self:
            status = False
            visit = rec.generated_plan_line_id.visit_id
            line_state = rec.generated_plan_line_id.state
            visit_state = visit.state if visit else False
            visit_process_state = visit.visit_process_state if visit else False

            if line_state == "skipped":
                status = "skipped"
            elif visit_state == "done" or visit_process_state == "done" or line_state == "visited":
                status = "done"
            elif line_state == "in_progress" or visit_state == "in_progress" or visit_process_state in ("checked_in", "counting", "reconciled", "collection_done", "ready_to_close"):
                status = "in_progress"
            elif rec.generated_plan_id and rec.generated_plan_id.state != "cancel":
                status = "pending"

            rec.execution_status = status

    @api.depends("weekday")
    def _compute_weekday_label(self):
        for rec in self:
            rec.weekday_label = WEEKDAY_LABELS.get(rec.weekday or "", "")

    @api.depends("weekday", "schedule_id.company_id.route_weekly_off_day")
    def _compute_is_off_day(self):
        for rec in self:
            rec.is_off_day = bool(
                rec.weekday
                and rec.schedule_id.company_id.route_weekly_off_day
                and rec.weekday == rec.schedule_id.company_id.route_weekly_off_day
            )

    @api.depends("schedule_id.week_start_date", "weekday", "schedule_id.company_id.route_week_start_day")
    def _compute_visit_date(self):
        for rec in self:
            rec.visit_date = compute_weekday_date(
                rec.schedule_id.week_start_date,
                rec.weekday,
                week_start_day=rec.schedule_id.company_id.route_week_start_day or "monday",
            )

    def _get_effective_weekday(self):
        self.ensure_one()
        return self.weekday or self.env.context.get("default_weekday") or "monday"

    def _get_parent_lines(self):
        self.ensure_one()
        return self.schedule_id.line_ids

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
        sibling_lines = self.env["route.weekly.schedule.line"]

        for line in self._get_parent_lines():
            if not line.outlet_id:
                continue
            if (line.weekday or "monday") != weekday:
                continue
            if self._is_current_line(line):
                continue
            sibling_lines |= line

        if not sibling_lines and self.schedule_id and self.schedule_id.id:
            real_id = self._origin.id or (self.id if isinstance(self.id, int) else False)
            domain = [
                ("schedule_id", "=", self.schedule_id.id),
                ("weekday", "=", weekday),
                ("outlet_id", "!=", False),
            ]
            if real_id:
                domain.append(("id", "!=", real_id))
            sibling_lines = self.search(domain)
        return sibling_lines

    def _get_duplicate_line(self):
        self.ensure_one()
        if not self.schedule_id or not self.outlet_id:
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
            ("schedule_id", "=", self.schedule_id.id),
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
        "schedule_id.line_ids.weekday",
        "schedule_id.line_ids.outlet_id",
        "schedule_id.line_ids.area_id",
        "schedule_id.line_ids.city_id",
    )
    def _compute_same_day_outlet_helpers(self):
        Outlet = self.env["route.outlet"]
        for rec in self:
            used_outlet_ids = rec._get_same_day_sibling_lines().mapped("outlet_id").ids
            rec.same_day_used_outlet_ids = Outlet.browse(used_outlet_ids)
            rec.available_outlet_ids = Outlet.browse(rec._get_available_outlet_ids())

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("route_weekly_schedule_skip_lock"):
            schedule_ids = {vals.get("schedule_id") for vals in vals_list if vals.get("schedule_id")}
            for schedule in self.env["route.weekly.schedule"].browse(list(schedule_ids)):
                if schedule.state != "draft":
                    raise UserError(
                        _(
                            "You cannot add weekly schedule lines after daily plans have already been generated. "
                            "Reset the weekly schedule safely first, or edit the daily route plans directly."
                        )
                    )
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
        if not self.env.context.get("route_weekly_schedule_skip_lock"):
            for rec in self:
                if rec.schedule_id and rec.schedule_id.state != "draft":
                    raise UserError(
                        _(
                            "You cannot edit weekly schedule lines after daily plans have already been generated. "
                            "Reset the weekly schedule safely first, or edit the daily route plans directly."
                        )
                    )
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

    def unlink(self):
        if not self.env.context.get("route_weekly_schedule_skip_lock"):
            for rec in self:
                if rec.schedule_id and rec.schedule_id.state != "draft":
                    raise UserError(
                        _(
                            "You cannot remove weekly schedule lines after daily plans have already been generated. "
                            "Reset the weekly schedule safely first, or edit the daily route plans directly."
                        )
                    )
        return super().unlink()

    @api.onchange("weekday")
    def _onchange_weekday_warning(self):
        self.ensure_one()
        off_day = self.schedule_id.company_id.route_weekly_off_day
        response = {"domain": self._get_dynamic_domains()}
        if self._get_effective_weekday() and off_day and self._get_effective_weekday() == off_day:
            response["warning"] = {
                "title": _("Weekly Off Day"),
                "message": _(
                    "This stop is scheduled on the configured weekly off day. It will remain visible for review but will be skipped during daily plan generation."
                ),
            }
        return response

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
                    "Outlet %(outlet)s is already added on %(day)s in this weekly schedule. Choose another outlet for that day."
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

    @api.constrains("schedule_id", "weekday", "outlet_id")
    def _check_duplicate_outlet_per_day(self):
        for rec in self.filtered(lambda line: line.schedule_id and line.outlet_id):
            duplicate = self.search([
                ("id", "!=", rec.id),
                ("schedule_id", "=", rec.schedule_id.id),
                ("weekday", "=", rec.weekday or "monday"),
                ("outlet_id", "=", rec.outlet_id.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    "Outlet %(outlet)s is already added on %(day)s in this weekly schedule. Choose another outlet or keep only one line for that day."
                ) % {
                    "outlet": rec.outlet_id.display_name or rec.outlet_id.name,
                    "day": WEEKDAY_LABELS.get(rec.weekday or "", rec.weekday or ""),
                })
