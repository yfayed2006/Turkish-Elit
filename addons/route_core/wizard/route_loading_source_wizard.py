from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RouteLoadingSourceWizard(models.TransientModel):
    _name = "route.loading.source.wizard"
    _description = "Choose Vehicle Loading Source"

    plan_id = fields.Many2one(
        "route.plan",
        string="Route Plan",
        required=True,
        readonly=True,
    )
    proposal_id = fields.Many2one(
        "route.loading.proposal",
        string="Existing Proposal",
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        compute="_compute_company_id",
        store=False,
    )
    vehicle_id = fields.Many2one(
        "route.vehicle",
        string="Vehicle",
        related="plan_id.vehicle_id",
        readonly=True,
        store=False,
    )
    destination_location_id = fields.Many2one(
        "stock.location",
        string="Vehicle Location",
        related="vehicle_id.stock_location_id",
        readonly=True,
        store=False,
    )
    allowed_source_location_ids = fields.Many2many(
        "stock.location",
        string="Allowed Loading Source Locations",
        compute="_compute_allowed_source_location_ids",
        store=False,
    )
    source_location_id = fields.Many2one(
        "stock.location",
        string="Source Warehouse Location",
        required=True,
        domain="[('id', 'in', allowed_source_location_ids)]",
    )

    def _compute_company_id(self):
        for rec in self:
            rec.company_id = rec.plan_id.company_id or rec.env.company

    @api.depends("company_id", "plan_id", "plan_id.source_warehouse_id")
    def _compute_allowed_source_location_ids(self):
        for rec in self:
            rec.allowed_source_location_ids = rec._get_allowed_loading_source_locations()

    def _get_allowed_loading_source_locations(self):
        self.ensure_one()
        company = self.company_id or self.plan_id.company_id or self.env.company
        domain = []
        if company:
            domain.append(("company_id", "=", company.id))
        warehouses = self.env["stock.warehouse"].search(domain, order="name, id")
        locations = warehouses.mapped("lot_stock_id").filtered(lambda loc: loc and loc.usage == "internal")
        if self.plan_id.source_warehouse_id and self.plan_id.source_warehouse_id.lot_stock_id:
            plan_location = self.plan_id.source_warehouse_id.lot_stock_id
            if plan_location.usage == "internal" and plan_location not in locations:
                locations |= plan_location
        return locations

    def _get_default_loading_source_location(self):
        self.ensure_one()
        allowed_locations = self._get_allowed_loading_source_locations()
        plan_location = self.plan_id.source_warehouse_id.lot_stock_id if self.plan_id.source_warehouse_id else False
        if plan_location and plan_location in allowed_locations:
            return plan_location
        return allowed_locations[:1]

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        plan_id = vals.get("plan_id") or self.env.context.get("default_plan_id")
        if plan_id:
            wizard = self.new(vals)
            source = self.env["stock.location"].browse(vals.get("source_location_id")) if vals.get("source_location_id") else False
            allowed_locations = wizard._get_allowed_loading_source_locations()
            if not source or source not in allowed_locations:
                default_source = wizard._get_default_loading_source_location()
                vals["source_location_id"] = default_source.id if default_source else False
        return vals

    @api.onchange("plan_id", "company_id")
    def _onchange_plan_source_domain(self):
        for rec in self:
            allowed_locations = rec.allowed_source_location_ids
            if rec.source_location_id and rec.source_location_id in allowed_locations:
                continue
            default_source = rec._get_default_loading_source_location()
            rec.source_location_id = default_source

    def action_confirm(self):
        self.ensure_one()
        if not self.plan_id:
            raise UserError(_("This wizard is not linked to a route plan."))
        if not self.source_location_id:
            raise UserError(_("Please choose a source warehouse location."))
        if self.destination_location_id and self.source_location_id == self.destination_location_id:
            raise UserError(
                _("The source warehouse location and the vehicle location cannot be the same.")
            )
        allowed_locations = self.allowed_source_location_ids or self._get_allowed_loading_source_locations()
        if allowed_locations and self.source_location_id not in allowed_locations:
            raise UserError(
                _(
                    "Please choose a real warehouse stock location as the loading source. "
                    "Outlet, vehicle, return, damaged, expired, and consignment shelf locations cannot be used here."
                )
            )

        warehouse = self.env["stock.warehouse"].search([
            ("lot_stock_id", "=", self.source_location_id.id),
            ("company_id", "in", [False, self.plan_id.company_id.id]),
        ], order="company_id desc, id asc", limit=1)
        if warehouse and self.plan_id.source_warehouse_id != warehouse:
            self.plan_id.source_warehouse_id = warehouse.id

        proposal = self.plan_id._generate_loading_proposal_with_source(
            self.source_location_id,
            proposal=self.proposal_id,
        )
        return proposal._open_form_action()
