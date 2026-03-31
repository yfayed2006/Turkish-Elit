from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    return_damaged_location_id = fields.Many2one(
        "stock.location",
        string="Return Damaged Location",
        domain="[('usage', '=', 'internal')]",
        help="Internal stock location used for damaged returned products from route visits.",
    )

    return_near_expiry_location_id = fields.Many2one(
        "stock.location",
        string="Return Near Expiry Location",
        domain="[('usage', '=', 'internal')]",
        help="Internal stock location used for near expiry returned products from route visits.",
    )

    route_enable_lot_serial_tracking = fields.Boolean(
        string="Enable Lot/Serial Workflow",
        compute="_compute_route_feature_flags",
        inverse="_inverse_route_feature_flags",
        readonly=False,
        help="Show and enforce Route Sales Lot/Serial workflow where supported.",
    )

    route_enable_expiry_tracking = fields.Boolean(
        string="Enable Expiry Workflow",
        compute="_compute_route_feature_flags",
        inverse="_inverse_route_feature_flags",
        readonly=False,
        help="Show expiry information in Route Sales where lot workflow is enabled.",
    )


    route_enable_direct_sale = fields.Boolean(
        string="Enable Direct Sale",
        compute="_compute_route_feature_flags",
        inverse="_inverse_route_feature_flags",
        readonly=False,
        help="Enable Direct Sale workspace, orders, deliveries, payments, and related Route Sales actions.",
    )

    route_enable_direct_return = fields.Boolean(
        string="Enable Direct Return",
        compute="_compute_route_feature_flags",
        inverse="_inverse_route_feature_flags",
        readonly=False,
        help="Enable manual Direct Return workflow and related Route Sales actions.",
    )

    def _route_feature_param_key(self, feature_name):
        self.ensure_one()
        return f"route_core.{feature_name}.{self.id}"

    def _compute_route_feature_flags(self):
        icp = self.env["ir.config_parameter"].sudo()
        for company in self:
            lot_enabled = icp.get_param(company._route_feature_param_key("enable_lot_serial_tracking"), default="1")
            expiry_enabled = icp.get_param(company._route_feature_param_key("enable_expiry_tracking"), default="1")
            direct_sale_enabled = icp.get_param(company._route_feature_param_key("enable_direct_sale"), default="1")
            direct_return_enabled = icp.get_param(company._route_feature_param_key("enable_direct_return"), default="1")
            company.route_enable_lot_serial_tracking = str(lot_enabled).lower() in ("1", "true", "yes")
            company.route_enable_expiry_tracking = (
                company.route_enable_lot_serial_tracking
                and str(expiry_enabled).lower() in ("1", "true", "yes")
            )
            company.route_enable_direct_sale = str(direct_sale_enabled).lower() in ("1", "true", "yes")
            company.route_enable_direct_return = (
                company.route_enable_direct_sale
                and str(direct_return_enabled).lower() in ("1", "true", "yes")
            )

    def _inverse_route_feature_flags(self):
        icp = self.env["ir.config_parameter"].sudo()
        for company in self:
            lot_enabled = bool(company.route_enable_lot_serial_tracking)
            expiry_enabled = bool(company.route_enable_expiry_tracking) and lot_enabled
            direct_sale_enabled = bool(company.route_enable_direct_sale)
            direct_return_enabled = bool(company.route_enable_direct_return) and direct_sale_enabled
            icp.set_param(company._route_feature_param_key("enable_lot_serial_tracking"), "1" if lot_enabled else "0")
            icp.set_param(company._route_feature_param_key("enable_expiry_tracking"), "1" if expiry_enabled else "0")
            icp.set_param(company._route_feature_param_key("enable_direct_sale"), "1" if direct_sale_enabled else "0")
            icp.set_param(company._route_feature_param_key("enable_direct_return"), "1" if direct_return_enabled else "0")
