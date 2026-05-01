from odoo import models, SUPERUSER_ID


class RouteVisit(models.Model):
    _inherit = "route.visit"

    def action_ux_confirm_refill(self):
        self.ensure_one()

        # This branch is used after the Missing Lots wizard has saved the selected
        # lots and is continuing the approved PDA workflow. At this point the
        # backend must complete the stock transfer internally, because salesperson
        # users can be intentionally restricted from reading product.product.
        if self.env.context.get("skip_missing_lot_check"):
            visit = self.with_user(SUPERUSER_ID).sudo()
            result = visit.action_confirm_refill_transfer()

            # If Odoo returns a stock validation wizard, keep it. Otherwise, bring
            # the salesperson back to the visit screen.
            if isinstance(result, dict) and result.get("res_model") not in (False, "route.visit"):
                return result
            return self._get_pda_form_action()

        return super().action_ux_confirm_refill()
