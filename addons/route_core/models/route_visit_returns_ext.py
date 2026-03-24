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

    def _action_open_returns_scan_wizard(self):
        self.ensure_one()

        if self.visit_process_state != "counting":
            raise UserError(
                _("Returns can only be recorded during the counting stage.")
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Additional Returns"),
            "res_model": "route.visit.return.scan.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_visit_id": self.id,
                "default_quantity": 1.0,
                "default_return_route": "vehicle",
            },
        }

    def _action_mark_no_returns(self):
        self.ensure_one()

        if self.visit_process_state != "counting":
            raise UserError(
                _("No Additional Returns can only be confirmed during the counting stage.")
            )


        self.write({
            "has_returns_declared": any((line.return_qty or 0.0) > 0 for line in self.line_ids),
            "returns_step_done": True,
        })

        return self._action_reopen_visit_form()

    def action_ux_returns_step(self):
        self.ensure_one()
        return self._action_open_returns_scan_wizard()

    def action_ux_no_returns(self):
        self.ensure_one()
        return self._action_mark_no_returns()

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
            "return_route": "vehicle",
        })

    def _add_return_qty(self, product, qty, return_route="vehicle"):
        self.ensure_one()

        if qty <= 0:
            raise UserError(_("Return quantity must be greater than zero."))

        if return_route not in ("vehicle", "damaged", "near_expiry"):
            raise UserError(_("Invalid return route."))

        line = self._find_or_create_visit_line_for_product(product)
        line.write({
            "return_qty": (line.return_qty or 0.0) + qty,
            "return_route": return_route or "vehicle",
        })

        self.write({
            "has_returns_declared": True,
            "returns_step_done": False,
        })

        return line
