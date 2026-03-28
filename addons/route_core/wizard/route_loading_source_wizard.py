from odoo import _, fields, models
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
    source_location_id = fields.Many2one(
        "stock.location",
        string="Source Warehouse Location",
        required=True,
        domain="['&', ('usage', '=', 'internal'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )

    def _compute_company_id(self):
        for rec in self:
            rec.company_id = rec.plan_id.company_id or rec.env.company

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
        proposal = self.plan_id._generate_loading_proposal_with_source(
            self.source_location_id,
            proposal=self.proposal_id,
        )
        return proposal._open_form_action()
