from datetime import date as pydate

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class RoutePlan(models.Model):
    _name = "route.plan"
    _description = "Daily Route Plan"
    _order = "date desc, id desc"

    name = fields.Char(
        string="Plan Reference",
        required=True,
        copy=False,
        readonly=True,
        default="New",
    )
    date = fields.Date(
        string="Plan Date",
        required=True,
        default=fields.Date.context_today,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        required=True,
        default=lambda self: self.env.user,
    )
    vehicle_id = fields.Many2one(
        "route.vehicle",
        string="Vehicle",
        required=True,
        ondelete="restrict",
    )
    area_id = fields.Many2one(
        "route.area",
        string="Area",
        ondelete="restrict",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
    )
    planning_finalized = fields.Boolean(
        string="Daily Planning Finalized",
        default=False,
        copy=False,
        help="Enable this after the supervisor finishes the vehicle's daily route planning. "
        "The loading proposal is generated only from a finalized daily plan.",
    )
    planning_finalized_datetime = fields.Datetime(
        string="Planning Finalized On",
        copy=False,
        readonly=True,
    )
    notes = fields.Text(string="Notes")

    line_ids = fields.One2many(
        "route.plan.line",
        "plan_id",
        string="Planned Visits",
    )
    line_count = fields.Integer(
        string="Visits Count",
        compute="_compute_line_counts",
    )
    visit_count = fields.Integer(
        string="Executed Visits",
        compute="_compute_line_counts",
    )
    pending_count = fields.Integer(
        string="Pending Visits",
        compute="_compute_line_counts",
    )
    visited_count = fields.Integer(
        string="Completed Visits",
        compute="_compute_line_counts",
    )
    skipped_count = fields.Integer(
        string="Skipped Visits",
        compute="_compute_line_counts",
    )
    in_progress_count = fields.Integer(
        string="In Progress Visits",
        compute="_compute_line_counts",
    )
    shortage_count = fields.Integer(
        string="Planned Shortages",
        compute="_compute_shortage_counts",
    )
    open_shortage_candidate_count = fields.Integer(
        string="Open Shortage Candidates",
        compute="_compute_shortage_counts",
    )

    area_summary = fields.Char(
        string="Areas",
        compute="_compute_plan_summaries",
        store=False,
    )
    outlet_summary = fields.Char(
        string="Outlets",
        compute="_compute_plan_summaries",
        store=False,
    )
    search_area_ids = fields.Many2many(
        "route.area",
        string="Search Areas",
        compute="_compute_search_panel_relations",
        store=True,
    )
    search_outlet_ids = fields.Many2many(
        "route.outlet",
        string="Search Outlets",
        compute="_compute_search_panel_relations",
        store=True,
    )
    previous_pending_visit_count = fields.Integer(
        string="Previous Pending Visits",
        compute="_compute_pending_review_stats",
    )
    previous_pending_outlet_summary = fields.Char(
        string="Previous Pending Outlets",
        compute="_compute_pending_review_stats",
    )
    has_previous_pending_visits = fields.Boolean(
        string="Has Previous Pending Visits",
        compute="_compute_pending_review_stats",
    )

    @api.depends("line_ids", "line_ids.state", "line_ids.visit_id", "line_ids.visit_id.state")
    def _compute_line_counts(self):
        for rec in self:
            lines = rec.line_ids
            rec.line_count = len(lines)
            rec.visit_count = len(lines.filtered(lambda l: l.visit_id))
            rec.pending_count = len(lines.filtered(lambda l: l.state == "pending"))
            rec.visited_count = len(lines.filtered(lambda l: l.state == "visited"))
            rec.skipped_count = len(lines.filtered(lambda l: l.state == "skipped"))
            rec.in_progress_count = len(
                lines.filtered(
                    lambda l: l.state == "in_progress"
                    or (l.visit_id and l.visit_id.state == "in_progress")
                )
            )

    @api.depends("line_ids.outlet_id", "area_id", "date")
    def _compute_shortage_counts(self):
        Shortage = self.env["route.shortage"]
        for rec in self:
            rec.shortage_count = Shortage.search_count([
                ("planned_route_plan_id", "=", rec.id),
                ("state", "in", ["planned", "open"]),
            ])

            candidate_domain = [("state", "=", "open")]
            if rec.area_id:
                candidate_domain.append(("area_id", "=", rec.area_id.id))
            rec.open_shortage_candidate_count = Shortage.search_count(candidate_domain)

    @api.depends(
        "area_id",
        "line_ids.area_id",
        "line_ids.outlet_id",
        "line_ids.sequence",
    )
    def _compute_plan_summaries(self):
        for rec in self:
            areas = rec.line_ids.mapped("area_id")
            outlets = rec.line_ids.mapped("outlet_id")

            area_names = [name for name in areas.mapped("name") if name]
            outlet_names = [name for name in outlets.mapped("name") if name]

            if not area_names and rec.area_id:
                area_names = [rec.area_id.name]

            unique_area_names = list(dict.fromkeys(area_names))
            unique_outlet_names = list(dict.fromkeys(outlet_names))

            rec.area_summary = self._format_summary_names(unique_area_names, max_items=2)
            rec.outlet_summary = self._format_summary_names(unique_outlet_names, max_items=2)

    @api.depends("area_id", "date", "line_ids.area_id", "line_ids.outlet_id", "line_ids.state")
    def _compute_pending_review_stats(self):
        for rec in self:
            pending_lines = rec._get_previous_pending_lines()
            rec.previous_pending_visit_count = len(pending_lines)
            rec.has_previous_pending_visits = bool(pending_lines)
            outlet_names = list(dict.fromkeys(pending_lines.mapped("outlet_id.name")))
            rec.previous_pending_outlet_summary = rec._format_summary_names(
                [name for name in outlet_names if name],
                max_items=3,
            )

    @api.depends("area_id", "line_ids.area_id", "line_ids.outlet_id")
    def _compute_search_panel_relations(self):
        for rec in self:
            area_ids = set(rec.line_ids.mapped("area_id").ids)
            if rec.area_id:
                area_ids.add(rec.area_id.id)

            rec.search_area_ids = [fields.Command.set(list(area_ids))]
            rec.search_outlet_ids = [fields.Command.set(rec.line_ids.mapped("outlet_id").ids)]

    @api.model
    def _format_summary_names(self, names, max_items=2):
        names = [n for n in names if n]
        if not names:
            return ""
        if len(names) <= max_items:
            return ", ".join(names)
        return "%s ..." % ", ".join(names[:max_items])

    def _get_effective_area_ids(self):
        self.ensure_one()
        area_ids = set(self.line_ids.mapped("area_id").ids)
        if self.area_id:
            area_ids.add(self.area_id.id)
        return list(area_ids)

    def _get_previous_pending_lines(self, outlet=None):
        self.ensure_one()
        if not self.date:
            return self.env["route.plan.line"]

        area_ids = self._get_effective_area_ids()
        if not area_ids:
            return self.env["route.plan.line"]

        domain = [
            ("state", "=", "pending"),
            ("area_id", "in", area_ids),
            ("plan_id", "!=", self.id),
            ("plan_id.date", "<", self.date),
        ]
        if outlet:
            domain.append(("outlet_id", "=", outlet.id))

        lines = self.env["route.plan.line"].search(domain, order="sequence asc, id asc")
        return lines.sorted(
            key=lambda line: (
                line.plan_id.date or pydate.min,
                line.sequence or 0,
                line.id or 0,
            )
        )

    def _ensure_no_unresolved_previous_pending(self, line):
        self.ensure_one()
        previous_pending = self._get_previous_pending_lines(outlet=line.outlet_id)[:1]
        if not previous_pending:
            return

        source_line = previous_pending[0]
        raise UserError(
            _(
                "There is an older pending visit for outlet '%(outlet)s' in route plan '%(plan)s' dated %(date)s. "
                "Please review pending visits first, then decide Carry Forward, Reschedule, or Cancel before starting a new visit for this outlet."
            )
            % {
                "outlet": source_line.outlet_id.display_name or _("Unknown Outlet"),
                "plan": source_line.plan_id.display_name or source_line.plan_id.name,
                "date": fields.Date.to_string(source_line.plan_id.date) if source_line.plan_id.date else _("Unknown Date"),
            }
        )

    def _get_or_create_plan_for_date(self, target_date, area=None):
        self.ensure_one()
        if not target_date:
            raise UserError(_("Please select a target date."))

        area = area or self.area_id or self.line_ids[:1].area_id
        if not area:
            raise UserError(_("Please set the route area first."))

        plan = self.search([
            ("date", "=", target_date),
            ("user_id", "=", self.user_id.id),
            ("vehicle_id", "=", self.vehicle_id.id),
            ("area_id", "=", area.id),
            ("state", "!=", "cancel"),
        ], limit=1)

        if plan:
            return plan

        return self.create({
            "date": target_date,
            "user_id": self.user_id.id,
            "vehicle_id": self.vehicle_id.id,
            "area_id": area.id,
            "notes": _("Auto-created from pending visit review of %s.") % (self.name,),
        })

    def _sync_state_from_lines(self):
        for rec in self:
            if rec.state == "cancel":
                continue

            if not rec.line_ids:
                new_state = "draft"
            else:
                line_states = set(rec.line_ids.mapped("state"))

                if line_states == {"pending"}:
                    new_state = "draft"
                elif line_states.issubset({"visited", "skipped"}):
                    new_state = "done"
                else:
                    new_state = "in_progress"

            if rec.state != new_state:
                rec.sudo().with_context(route_plan_skip_sync=True).write({"state": new_state})

    def _mark_planning_as_unfinalized(self):
        if self.env.context.get("route_plan_skip_loading_dirty"):
            return
        for rec in self.filtered("planning_finalized"):
            rec.with_context(route_plan_skip_loading_dirty=True).write(
                {
                    "planning_finalized": False,
                    "planning_finalized_datetime": False,
                }
            )

    def _ensure_plan_editable(self, action_label=None):
        for rec in self:
            if rec.planning_finalized:
                if action_label:
                    raise UserError(
                        _(
                            "You cannot %s after Finalize Daily Plan. "
                            "Please click 'Reopen Daily Plan' first."
                        )
                        % action_label
                    )
                raise UserError(
                    _(
                        "This route plan is locked because Daily Planning has been finalized. "
                        "Please click 'Reopen Daily Plan' first."
                    )
                )

    def _get_active_plan_lines(self, exclude_line=None):
        self.ensure_one()
        active_lines = self.line_ids.filtered(
            lambda l: l.state == "in_progress"
            or (l.visit_id and l.visit_id.state == "in_progress")
        )
        if exclude_line:
            active_lines = active_lines.filtered(lambda l: l.id != exclude_line.id)
        return active_lines

    def _ensure_single_active_visit(self, current_line=None):
        for rec in self:
            exclude_line = current_line if current_line and current_line.plan_id == rec else None
            active_lines = rec._get_active_plan_lines(exclude_line=exclude_line)
            if not active_lines:
                continue

            active_line = active_lines[0]
            outlet_name = active_line.outlet_id.display_name or _("Unknown Outlet")
            visit_label = _("draft visit")
            if active_line.visit_id:
                visit_label = active_line.visit_id.display_name or active_line.visit_id.name

            raise UserError(
                _(
                    "There is already an active visit on this route plan for outlet '%(outlet)s' (%(visit)s). "
                    "Please open or finish the current visit before starting another one."
                )
                % {
                    "outlet": outlet_name,
                    "visit": visit_label,
                }
            )

    def action_open_pending_visit_review_wizard(self):
        self.ensure_one()

        pending_lines = self._get_previous_pending_lines()
        if not pending_lines:
            raise UserError(_("There are no previous pending visits for this route plan area."))

        wizard = self.env["route.plan.pending.visit.review.wizard"].create({
            "plan_id": self.id,
            "line_ids": [
                fields.Command.create({
                    "source_line_id": line.id,
                    "decision": "carry_forward",
                })
                for line in pending_lines
            ],
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Review Pending Visits"),
            "res_model": "route.plan.pending.visit.review.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_load_previous_pending_visits(self):
        self.ensure_one()
        return self.action_open_pending_visit_review_wizard()

    def action_finalize_daily_plan(self):
        for rec in self:
            if rec.state == "cancel":
                raise UserError(_("You cannot finalize a cancelled route plan."))
            if not rec.vehicle_id:
                raise UserError(_("Please select a vehicle before finalizing the daily plan."))
            if not getattr(rec.vehicle_id, "stock_location_id", False):
                raise UserError(
                    _("Vehicle '%s' does not have a vehicle stock location.")
                    % (rec.vehicle_id.display_name,)
                )
            if not rec.line_ids.filtered("outlet_id"):
                raise UserError(
                    _("Please complete the vehicle's daily route planning before finalizing it.")
                )
            rec.with_context(route_plan_skip_loading_dirty=True).write(
                {
                    "planning_finalized": True,
                    "planning_finalized_datetime": fields.Datetime.now(),
                }
            )
        return True

    def action_reopen_daily_plan(self):
        self.with_context(route_plan_skip_loading_dirty=True).write(
            {
                "planning_finalized": False,
                "planning_finalized_datetime": False,
            }
        )
        return True

    def _prepare_visit_vals(self, line):
        self.ensure_one()
        return {
            "date": self.date,
            "outlet_id": line.outlet_id.id,
            "partner_id": line.partner_id.id if line.partner_id else False,
            "area_id": line.area_id.id if line.area_id else (self.area_id.id if self.area_id else False),
            "vehicle_id": self.vehicle_id.id,
            "user_id": self.user_id.id,
            "notes": line.note or False,
        }

    def _create_visit_for_line(self, line):
        self.ensure_one()

        if line.visit_id:
            self._ensure_single_active_visit(current_line=line)
            if line.state not in ("visited", "skipped") and line.visit_id.state not in ("done", "cancel"):
                line.write({"state": "in_progress"})
            return line.visit_id

        if not self.planning_finalized:
            raise UserError(
                _(
                    "You cannot start visits before finalizing the daily plan. "
                    "Please click 'Finalize Daily Plan' first."
                )
            )

        self._ensure_single_active_visit(current_line=line)
        self._ensure_no_unresolved_previous_pending(line)

        if not line.outlet_id:
            raise UserError(_("Cannot create a visit for a route line without an outlet."))

        visit_vals = self._prepare_visit_vals(line)
        visit = self.env["route.visit"].with_context(
            route_plan_allow_visit_create=True
        ).create(visit_vals)

        line.write({"visit_id": visit.id, "state": "in_progress"})
        return visit

    def _get_open_shortage_domain(self):
        self.ensure_one()
        domain = [("state", "=", "open")]
        if self.area_id:
            domain.append(("area_id", "=", self.area_id.id))
        return domain

    def action_add_open_shortages(self):
        self.ensure_one()
        self._ensure_plan_editable(_("add open shortages"))

        shortages = self.env["route.shortage"].search(
            self._get_open_shortage_domain(),
            order="date asc, id asc",
        )
        if not shortages:
            raise UserError(_("There are no open shortages to add to this route plan."))

        existing_lines_by_outlet = {
            line.outlet_id.id: line
            for line in self.line_ids.filtered("outlet_id")
        }
        max_sequence = max(self.line_ids.mapped("sequence") or [0])

        for shortage in shortages:
            if not shortage.outlet_id:
                continue

            existing_line = existing_lines_by_outlet.get(shortage.outlet_id.id)
            note_fragment = _("Open shortage: %s") % shortage.name

            if existing_line:
                vals = {}
                if existing_line.visit_id and existing_line.visit_id.state in ("done", "cancel"):
                    vals["visit_id"] = False
                    vals["state"] = "pending"
                current_note = (existing_line.note or "").strip()
                if shortage.name not in current_note:
                    vals["note"] = (current_note + "\n" + note_fragment).strip()
                if vals:
                    existing_line.write(vals)
            else:
                max_sequence += 10
                line = self.env["route.plan.line"].create({
                    "plan_id": self.id,
                    "sequence": max_sequence,
                    "area_id": shortage.outlet_id.area_id.id if shortage.outlet_id.area_id else (self.area_id.id if self.area_id else False),
                    "outlet_id": shortage.outlet_id.id,
                    "note": note_fragment,
                })
                existing_lines_by_outlet[shortage.outlet_id.id] = line

            shortage.write({
                "state": "planned",
                "planned_date": self.date,
                "planned_route_plan_id": self.id,
            })

        return self.action_view_shortages()

    def action_view_visits(self):
        self.ensure_one()

        visits = self.line_ids.mapped("visit_id")
        action = self.env.ref("route_core.action_route_visit").read()[0]
        action["domain"] = [("id", "in", visits.ids)]

        if len(visits) == 1:
            action["res_id"] = visits.id
            action["views"] = [(False, "form")]
        else:
            action["views"] = [(False, "list"), (False, "form")]

        return action

    def action_view_shortages(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_shortage").read()[0]
        action["domain"] = [("planned_route_plan_id", "=", self.id)]
        action["context"] = {
            **self.env.context,
            "default_planned_route_plan_id": self.id,
            "search_default_filter_planned": 0,
            "search_default_filter_open": 0,
        }
        return action

    def action_open_add_area_outlets_wizard(self):
        self.ensure_one()
        self._ensure_plan_editable(_("add visits by area"))
        return {
            "type": "ir.actions.act_window",
            "name": _("Add Visits by Area"),
            "res_model": "route.plan.add.area.outlets.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_plan_id": self.id,
                "default_area_id": self.area_id.id if self.area_id else False,
            },
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("route.plan") or "New"
        records = super().create(vals_list)
        records._sync_state_from_lines()
        return records

    def write(self, vals):
        protected_fields = {"date", "user_id", "vehicle_id"}
        planning_change_fields = {"date", "user_id", "vehicle_id", "area_id"}
        allowed_locked_write_fields = {"planning_finalized", "planning_finalized_datetime", "state"}

        if protected_fields.intersection(vals.keys()):
            for rec in self:
                if rec.line_ids.filtered("visit_id"):
                    raise UserError(
                        _(
                            "You cannot change Plan Date, Salesperson, or Vehicle after visits have already been created from this plan."
                        )
                    )

        restricted_locked_fields = set(vals.keys()) - allowed_locked_write_fields
        if restricted_locked_fields and not self.env.context.get("route_plan_skip_locked_check"):
            for rec in self:
                if rec.planning_finalized:
                    raise UserError(
                        _(
                            "This route plan is locked after Finalize Daily Plan. "
                            "Please click 'Reopen Daily Plan' first before editing it."
                        )
                    )

        result = super().write(vals)

        if self.env.context.get("route_plan_skip_sync"):
            return result

        if "state" not in vals or vals.get("state") != "cancel":
            self._sync_state_from_lines()

        if planning_change_fields.intersection(vals.keys()) and not self.env.context.get(
            "route_plan_skip_loading_dirty"
        ):
            self._mark_planning_as_unfinalized()

        return result
