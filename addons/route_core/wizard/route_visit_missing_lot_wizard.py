from odoo import _, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError


class RouteVisitMissingLotWizard(models.TransientModel):
    _name = "route.visit.missing.lot.wizard"
    _description = "Route Visit Missing Lot Wizard"

    visit_id = fields.Many2one("route.visit", string="Visit", required=True, readonly=True)
    resume_action = fields.Selection(
        [
            ("reconcile_count", "Reconcile Count"),
            ("confirm_return_transfers", "Confirm Return Transfers"),
            ("confirm_refill", "Confirm Refill"),
            ("create_sale_order", "Create Sale Order"),
        ],
        string="Continue With",
        required=True,
        readonly=True,
    )
    line_ids = fields.One2many(
        "route.visit.missing.lot.wizard.line",
        "wizard_id",
        string="Missing Lot Lines",
    )

    def _save_selected_lots(self):
        self.ensure_one()
        wizard = self.with_user(SUPERUSER_ID).sudo()

        if not wizard.line_ids:
            raise UserError(_("There are no missing lot lines to complete."))

        missing = wizard.line_ids.filtered(lambda line: not line.lot_id)
        if missing:
            raise UserError(_("Please select a Lot/Serial Number for every listed product before continuing."))

        for line in wizard.line_ids:
            line.visit_line_id.with_user(SUPERUSER_ID).sudo().write({"lot_id": line.lot_id.id})

    def action_save_only(self):
        self.ensure_one()
        self._save_selected_lots()
        return self.visit_id._get_pda_form_action()

    def action_save_and_continue(self):
        self.ensure_one()
        self._save_selected_lots()

        visit = (
            self.env["route.visit"]
            .with_user(SUPERUSER_ID)
            .sudo()
            .browse(self.visit_id.id)
            .with_context(skip_missing_lot_check=True)
        )
        resume_action = self.with_user(SUPERUSER_ID).sudo().resume_action

        if resume_action == "reconcile_count":
            return visit.action_ux_reconcile_count()
        if resume_action == "confirm_return_transfers":
            return visit.action_ux_confirm_return_transfers()
        if resume_action == "confirm_refill":
            return visit.action_ux_confirm_refill()
        if resume_action == "create_sale_order":
            return visit.action_create_sale_order()
        return self.visit_id._get_pda_form_action()


class RouteVisitMissingLotWizardLine(models.TransientModel):
    _name = "route.visit.missing.lot.wizard.line"
    _description = "Route Visit Missing Lot Wizard Line"

    wizard_id = fields.Many2one(
        "route.visit.missing.lot.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )
    visit_line_id = fields.Many2one(
        "route.visit.line",
        string="Visit Line",
        required=True,
        readonly=True,
    )
    product_ref_id = fields.Integer(
        string="Product ID",
        readonly=True,
    )
    product_display_name = fields.Char(
        string="Product",
        readonly=True,
    )
    required_qty = fields.Float(
        string="Qty Requiring Lot",
        readonly=True,
    )
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lot/Serial",
        required=False,
    )
