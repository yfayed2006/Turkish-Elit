from odoo import fields, models

from .route_schedule_common import WEEKDAY_SELECTION


class ResCompany(models.Model):
    _inherit = "res.company"

    route_week_start_day = fields.Selection(
        WEEKDAY_SELECTION,
        string="Route Week Start Day",
        compute="_compute_route_week_start_day",
        inverse="_inverse_route_week_start_day",
        readonly=False,
        help="Defines which weekday is treated as the first day of the route planning week.",
    )
    route_weekly_off_day = fields.Selection(
        WEEKDAY_SELECTION,
        string="Weekly Off Day",
        compute="_compute_route_weekly_off_day",
        inverse="_inverse_route_weekly_off_day",
        readonly=False,
        help="Weekly off day used by weekly route schedules to skip automatic daily plan generation for that day.",
    )

    def _compute_route_week_start_day(self):
        icp = self.env["ir.config_parameter"].sudo()
        for company in self:
            value = icp.get_param(company._route_feature_param_key("week_start_day"), default="monday")
            company.route_week_start_day = value if value in dict(WEEKDAY_SELECTION) else "monday"

    def _inverse_route_week_start_day(self):
        icp = self.env["ir.config_parameter"].sudo()
        valid_codes = dict(WEEKDAY_SELECTION)
        for company in self:
            value = company.route_week_start_day or "monday"
            if value not in valid_codes:
                value = "monday"
            icp.set_param(company._route_feature_param_key("week_start_day"), value)

    def _compute_route_weekly_off_day(self):
        icp = self.env["ir.config_parameter"].sudo()
        for company in self:
            value = icp.get_param(company._route_feature_param_key("weekly_off_day"), default="friday")
            company.route_weekly_off_day = value if value in dict(WEEKDAY_SELECTION) else "friday"

    def _inverse_route_weekly_off_day(self):
        icp = self.env["ir.config_parameter"].sudo()
        valid_codes = dict(WEEKDAY_SELECTION)
        for company in self:
            value = company.route_weekly_off_day or "friday"
            if value not in valid_codes:
                value = "friday"
            icp.set_param(company._route_feature_param_key("weekly_off_day"), value)
