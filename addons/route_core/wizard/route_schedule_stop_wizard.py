from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from ..models.route_schedule_common import WEEKDAY_SELECTION, WEEKDAY_LABELS


class RouteScheduleStopWizard(models.TransientModel):
    _name = "route.schedule.stop.wizard"
    _description = "Route Schedule Stop Wizard"

    template_id = fields.Many2one(
        "route.schedule.template",
        string="Weekly Visit Template",
        readonly=True,
        ondelete="cascade",
    )
    schedule_id = fields.Many2one(
        "route.weekly.schedule",
        string="Weekly Schedule",
        readonly=True,
        ondelete="cascade",
    )
    weekday = fields.Selection(
        WEEKDAY_SELECTION,
        string="Weekday",
        required=True,
        default="monday",
        readonly=True,
    )
    weekday_label = fields.Char(string="Weekday Label", compute="_compute_weekday_label")
    title = fields.Char(string="Title", compute="_compute_title")
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
    available_outlet_ids = fields.Many2many(
        "route.outlet",
        string="Available Outlets",
        compute="_compute_available_outlet_ids",
    )
    outlet_ids = fields.Many2many(
        "route.outlet",
        string="Outlets",
        domain="[('id', 'in', available_outlet_ids)]",
    )
    note = fields.Text(string="Line Note")

    @api.depends("weekday")
    def _compute_weekday_label(self):
        for rec in self:
            rec.weekday_label = WEEKDAY_LABELS.get(rec.weekday or "", rec.weekday or "")

    @api.depends("weekday")
    def _compute_title(self):
        for rec in self:
            day_label = WEEKDAY_LABELS.get(rec.weekday or "", rec.weekday or "")
            rec.title = _("Create %(day)s Stops") % {"day": day_label}

    def _get_parent_record(self):
        self.ensure_one()
        if self.template_id:
            return self.template_id, "template"
        if self.schedule_id:
            return self.schedule_id, "schedule"
        return False, False

    def _get_parent_line_model(self):
        self.ensure_one()
        if self.template_id:
            return self.env["route.schedule.template.line"], "template_id"
        if self.schedule_id:
            return self.env["route.weekly.schedule.line"], "schedule_id"
        raise UserError(_("Open this wizard from a weekly visit template or weekly schedule."))

    def _get_used_outlet_ids(self):
        self.ensure_one()
        parent, _parent_type = self._get_parent_record()
        if not parent:
            return []
        return parent.line_ids.filtered(lambda line: (line.weekday or "monday") == (self.weekday or "monday")).mapped("outlet_id").ids

    @api.depends(
        "city_id",
        "area_id",
        "weekday",
        "template_id.line_ids.weekday",
        "template_id.line_ids.outlet_id",
        "schedule_id.line_ids.weekday",
        "schedule_id.line_ids.outlet_id",
    )
    def _compute_available_outlet_ids(self):
        Outlet = self.env["route.outlet"]
        for rec in self:
            if not rec.area_id:
                rec.available_outlet_ids = Outlet.browse()
                continue
            domain = [("area_id", "=", rec.area_id.id)]
            used_outlet_ids = rec._get_used_outlet_ids()
            if used_outlet_ids:
                domain.append(("id", "not in", used_outlet_ids))
            rec.available_outlet_ids = Outlet.search(domain)

    @api.onchange("city_id")
    def _onchange_city_id(self):
        for rec in self:
            if rec.area_id and rec.area_id.city_id != rec.city_id:
                rec.area_id = False
            rec.outlet_ids = [(5, 0, 0)]

    @api.onchange("area_id")
    def _onchange_area_id(self):
        for rec in self:
            if rec.area_id and rec.area_id.city_id != rec.city_id:
                rec.city_id = rec.area_id.city_id
            valid_outlets = rec.available_outlet_ids
            rec.outlet_ids = [(6, 0, rec.outlet_ids.filtered(lambda outlet: outlet in valid_outlets).ids)]

    def _reopen_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.title,
            "res_model": "route.schedule.stop.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
            "context": dict(self.env.context),
        }

    def action_select_all_area_outlets(self):
        self.ensure_one()
        if not self.area_id:
            raise UserError(_("Please select an area first."))
        self.outlet_ids = [(6, 0, self.available_outlet_ids.ids)]
        return self._reopen_action()

    def action_clear_selection(self):
        self.ensure_one()
        self.outlet_ids = [(5, 0, 0)]
        return self._reopen_action()

    def _prepare_line_vals_list(self):
        self.ensure_one()
        line_model, parent_field = self._get_parent_line_model()
        _line_model = line_model
        parent, _parent_type = self._get_parent_record()
        next_sequence = max(parent.line_ids.mapped("sequence") or [0]) + 10
        vals_list = []
        for outlet in self.outlet_ids.sorted(key=lambda record: (record.area_id.name or "", record.name or "", record.id)):
            vals_list.append({
                parent_field: parent.id,
                "sequence": next_sequence,
                "weekday": self.weekday,
                "city_id": outlet.area_id.city_id.id,
                "area_id": outlet.area_id.id,
                "outlet_id": outlet.id,
                "note": self.note,
            })
            next_sequence += 10
        return vals_list

    def action_save(self):
        self.ensure_one()
        parent, parent_type = self._get_parent_record()
        if not parent:
            raise UserError(_("Please open this wizard from a weekly visit template or weekly schedule."))
        if not self.city_id:
            raise UserError(_("Please select a city."))
        if not self.area_id:
            raise UserError(_("Please select an area."))
        if not self.outlet_ids:
            raise UserError(_("Please select at least one outlet."))

        used_outlet_ids = set(self._get_used_outlet_ids())
        duplicate_outlets = self.outlet_ids.filtered(lambda outlet: outlet.id in used_outlet_ids)
        if duplicate_outlets:
            day_label = WEEKDAY_LABELS.get(self.weekday or "", self.weekday or "")
            raise ValidationError(_(
                "Some selected outlets are already added on %(day)s. Remove them from the selection and try again: %(outlets)s"
            ) % {
                "day": day_label,
                "outlets": ", ".join(duplicate_outlets.mapped("display_name")),
            })

        line_model, _parent_field = self._get_parent_line_model()
        vals_list = self._prepare_line_vals_list()
        if not vals_list:
            raise UserError(_("There are no available outlets to add for this area and day."))
        line_model.create(vals_list)

        return {"type": "ir.actions.act_window_close"}
