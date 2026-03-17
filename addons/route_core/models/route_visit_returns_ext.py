from odoo import _, fields, models
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _inherit = "route.visit"

    returns_step_done = fields.Boolean(
        string="Returns Step Done",
        default=False,
        copy=False,
    )

    has_returns_declared = fields.Boolean(
        string="Has Returns Declared",
        default=False,
        copy=False,
    )

    def _action_reopen_visit_form(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Visit"),
            "res_model": "route.visit",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_ux_returns_step(self):
        self.ensure_one()
        if self.visit_process_state != "counting":
            raise UserError(_("Returns can only be recorded during the counting stage."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Scan Returns"),
            "res_model": "route.visit.return.scan.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_visit_id": self.id,
                "default_quantity": 1.0,
            },
        }

    def action_ux_no_returns(self):
        self.ensure_one()
        if self.visit_process_state != "counting":
            raise UserError(_("No Returns can only be confirmed during the counting stage."))

        self.write({
            "has_returns_declared": False,
            "returns_step_done": True,
        })
        return self._action_reopen_visit_form()

    def _find_or_create_visit_line_for_product(self, product):
        self.ensure_one()
        line = self.line_ids.filtered(lambda l: l.product_id == product)[:1]
        if line:
            return line

        return self.env["route.visit.line"].create({
            "visit_id": self.id,
            "product_id": product.id,
            "barcode": product.barcode or "",
            "uom_id": product.uom_id.id,
            "unit_price": getattr(product, "lst_price", 0.0),
        })

    def _add_return_qty(self, product, qty):
        self.ensure_one()

        if qty <= 0:
            raise UserError(_("Return quantity must be greater than zero."))

        line = self._find_or_create_visit_line_for_product(product)
        line.return_qty = (line.return_qty or 0.0) + qty

        self.write({
            "has_returns_declared": True,
        })
        return line
