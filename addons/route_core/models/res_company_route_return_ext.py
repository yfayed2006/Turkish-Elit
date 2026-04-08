from odoo import api, fields, models


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
        compute="_compute_route_enable_lot_serial_tracking",
        inverse="_inverse_route_enable_lot_serial_tracking",
        readonly=False,
        help="Show and enforce Route Sales Lot/Serial workflow where supported.",
    )

    route_enable_expiry_tracking = fields.Boolean(
        string="Enable Expiry Workflow",
        compute="_compute_route_enable_expiry_tracking",
        inverse="_inverse_route_enable_expiry_tracking",
        readonly=False,
        help="Show expiry information in Route Sales where lot workflow is enabled.",
    )

    route_operation_mode = fields.Selection(
        [("consignment", "Consignment Route"), ("direct_sales", "Direct Sales Route"), ("hybrid", "Hybrid Route")],
        string="Route Operation Mode",
        compute="_compute_route_operation_mode",
        inverse="_inverse_route_operation_mode",
        readonly=False,
        help="Consignment Route = shelf count, reconcile, refill, and visit collection. Direct Sales Route = outlet stops for sales, delivery, and payment without shelf count. Hybrid Route = both workflows are available.",
    )

    route_enable_direct_sale = fields.Boolean(
        string="Enable Direct Sale",
        compute="_compute_route_enable_direct_sale",
        inverse="_inverse_route_enable_direct_sale",
        readonly=False,
        help="Enable Direct Sale workspace, orders, deliveries, payments, and related Route Sales actions.",
    )

    route_enable_direct_return = fields.Boolean(
        string="Enable Direct Return",
        compute="_compute_route_enable_direct_return",
        inverse="_inverse_route_enable_direct_return",
        readonly=False,
        help="Enable manual Direct Return workflow and related Route Sales actions.",
    )


    route_vehicle_loading_workflow = fields.Selection(
        [
            ("disabled", "Disabled"),
            ("optional", "Optional"),
            ("required", "Required"),
        ],
        string="Vehicle Loading Workflow",
        compute="_compute_route_vehicle_loading_workflow",
        inverse="_inverse_route_vehicle_loading_workflow",
        readonly=False,
        help="Disabled = supervisors skip the loading proposal and vehicle transfer can be handled manually. Optional = loading proposal is available but does not block route execution. Required = visits cannot start until an approved loading proposal exists.",
    )

    def _route_feature_param_key(self, feature_name):
        self.ensure_one()
        return f"route_core.{feature_name}.{self.id}"

    def _route_param_is_enabled(self, feature_name, default="1"):
        self.ensure_one()
        value = self.env["ir.config_parameter"].sudo().get_param(
            self._route_feature_param_key(feature_name), default=default
        )
        return str(value).lower() in ("1", "true", "yes")

    def _set_route_param_enabled(self, feature_name, enabled):
        self.ensure_one()
        self.env["ir.config_parameter"].sudo().set_param(
            self._route_feature_param_key(feature_name), "1" if enabled else "0"
        )

    def _compute_route_enable_lot_serial_tracking(self):
        for company in self:
            company.route_enable_lot_serial_tracking = company._route_param_is_enabled(
                "enable_lot_serial_tracking", default="1"
            )

    def _inverse_route_enable_lot_serial_tracking(self):
        for company in self:
            company._set_route_param_enabled(
                "enable_lot_serial_tracking", bool(company.route_enable_lot_serial_tracking)
            )
            if not company.route_enable_lot_serial_tracking:
                company._set_route_param_enabled("enable_expiry_tracking", False)
                company.route_enable_expiry_tracking = False

    def _compute_route_enable_expiry_tracking(self):
        for company in self:
            if not company.route_enable_lot_serial_tracking:
                company.route_enable_expiry_tracking = False
            else:
                company.route_enable_expiry_tracking = company._route_param_is_enabled(
                    "enable_expiry_tracking", default="1"
                )

    def _inverse_route_enable_expiry_tracking(self):
        for company in self:
            expiry_enabled = bool(company.route_enable_expiry_tracking) and bool(company.route_enable_lot_serial_tracking)
            company._set_route_param_enabled("enable_expiry_tracking", expiry_enabled)
            if not company.route_enable_lot_serial_tracking:
                company.route_enable_expiry_tracking = False

    def _compute_route_operation_mode(self):
        icp = self.env["ir.config_parameter"].sudo()
        for company in self:
            value = icp.get_param(company._route_feature_param_key("operation_mode"), default="hybrid")
            company.route_operation_mode = value if value in ("consignment", "direct_sales", "hybrid") else "hybrid"

    def _inverse_route_operation_mode(self):
        icp = self.env["ir.config_parameter"].sudo()
        for company in self:
            value = company.route_operation_mode or "hybrid"
            if value not in ("consignment", "direct_sales", "hybrid"):
                value = "hybrid"
            icp.set_param(company._route_feature_param_key("operation_mode"), value)

    def _compute_route_enable_direct_sale(self):
        for company in self:
            company.route_enable_direct_sale = company._route_param_is_enabled(
                "enable_direct_sale", default="1"
            )

    def _inverse_route_enable_direct_sale(self):
        for company in self:
            company._set_route_param_enabled("enable_direct_sale", bool(company.route_enable_direct_sale))

    def _compute_route_enable_direct_return(self):
        for company in self:
            company.route_enable_direct_return = company._route_param_is_enabled(
                "enable_direct_return", default="1"
            )

    def _inverse_route_enable_direct_return(self):
        for company in self:
            company._set_route_param_enabled("enable_direct_return", bool(company.route_enable_direct_return))

    @api.onchange("route_enable_lot_serial_tracking")
    def _onchange_route_enable_lot_serial_tracking(self):
        if not self.route_enable_lot_serial_tracking:
            self.route_enable_expiry_tracking = False

    def route_operation_allows_consignment(self):
        self.ensure_one()
        return self.route_operation_mode in ("consignment", "hybrid")

    def route_operation_allows_direct_sale(self):
        self.ensure_one()
        return self.route_operation_mode in ("direct_sales", "hybrid")


    def route_vehicle_loading_is_enabled(self):
        self.ensure_one()
        return (self.route_vehicle_loading_workflow or "optional") in ("optional", "required")

    def route_vehicle_loading_is_required(self):
        self.ensure_one()
        return (self.route_vehicle_loading_workflow or "optional") == "required"
