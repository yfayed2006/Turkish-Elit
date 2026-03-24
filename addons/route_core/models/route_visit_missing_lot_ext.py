from odoo import _, models
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _inherit = "route.visit"

    def _get_missing_lot_lines(self, purpose="any"):
        self.ensure_one()
        lines = self.line_ids.filtered(
            lambda line: line.product_id
            and getattr(line.product_id, "tracking", "none") in ("lot", "serial")
            and not line.lot_id
        )

        if purpose in ("reconcile", "sale_order"):
            lines = lines.filtered(lambda line: (line.sold_qty or 0.0) > 0)
        elif purpose == "return":
            lines = lines.filtered(lambda line: (line.return_qty or 0.0) > 0)
        elif purpose == "refill":
            lines = lines.filtered(lambda line: (line.supplied_qty or 0.0) > 0)
        else:
            lines = lines.filtered(
                lambda line: (line.sold_qty or 0.0) > 0
                or (line.return_qty or 0.0) > 0
                or (line.supplied_qty or 0.0) > 0
            )

        return lines

    def _get_missing_lot_required_qty(self, line, purpose):
        self.ensure_one()
        if purpose in ("reconcile", "sale_order"):
            return line.sold_qty or 0.0
        if purpose == "return":
            return line.return_qty or 0.0
        if purpose == "refill":
            return line.supplied_qty or 0.0
        return max(line.sold_qty or 0.0, line.return_qty or 0.0, line.supplied_qty or 0.0)

    def _open_missing_lots_wizard(self, resume_action):
        self.ensure_one()
        purpose_map = {
            "reconcile_count": "reconcile",
            "confirm_return_transfers": "return",
            "confirm_refill": "refill",
            "create_sale_order": "sale_order",
        }
        purpose = purpose_map.get(resume_action, "any")
        missing_lines = self._get_missing_lot_lines(purpose=purpose)
        if not missing_lines:
            return False

        wizard = self.env["route.visit.missing.lot.wizard"].create({
            "visit_id": self.id,
            "resume_action": resume_action,
            "line_ids": [
                (0, 0, {
                    "visit_line_id": line.id,
                    "product_id": line.product_id.id,
                    "required_qty": self._get_missing_lot_required_qty(line, purpose),
                    "lot_id": line.lot_id.id,
                })
                for line in missing_lines
            ],
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Complete Missing Lots"),
            "res_model": "route.visit.missing.lot.wizard",
            "view_mode": "form",
            "res_id": wizard.id,
            "target": "new",
        }

    def action_open_missing_lots_wizard(self):
        self.ensure_one()
        action = self._open_missing_lots_wizard("reconcile_count")
        if action:
            return action
        raise UserError(_("There are no missing Lot/Serial assignments for this visit."))

    def action_ux_reconcile_count(self):
        self.ensure_one()
        if not self.env.context.get("skip_missing_lot_check"):
            action = self._open_missing_lots_wizard("reconcile_count")
            if action:
                return action
        return super().action_ux_reconcile_count()

    def action_ux_confirm_refill(self):
        self.ensure_one()
        if not self.env.context.get("skip_missing_lot_check"):
            action = self._open_missing_lots_wizard("confirm_refill")
            if action:
                return action
        return super().action_ux_confirm_refill()

    def action_ux_confirm_return_transfers(self):
        self.ensure_one()
        if not self.env.context.get("skip_missing_lot_check"):
            action = self._open_missing_lots_wizard("confirm_return_transfers")
            if action:
                return action
        return super().action_ux_confirm_return_transfers()

    def action_create_sale_order(self):
        self.ensure_one()
        if not self.env.context.get("skip_missing_lot_check"):
            action = self._open_missing_lots_wizard("create_sale_order")
            if action:
                return action
        return super().action_create_sale_order()

    def _fill_move_line_qty_done(self, picking):
        self.ensure_one()
        for move in picking.move_ids:
            qty = move.product_uom_qty or 0.0
            if qty <= 0:
                continue

            line = move.route_visit_line_id or self.line_ids.filtered(lambda l: l.product_id == move.product_id)[:1]
            tracking = getattr(move.product_id, "tracking", "none") or "none"
            lot = line.lot_id if line and tracking in ("lot", "serial") else False

            if lot:
                if move.move_line_ids:
                    move.move_line_ids.unlink()
                self.env["stock.move.line"].create({
                    "move_id": move.id,
                    "picking_id": picking.id,
                    "product_id": move.product_id.id,
                    "product_uom_id": move.product_uom.id,
                    "quantity": qty,
                    "location_id": move.location_id.id,
                    "location_dest_id": move.location_dest_id.id,
                    "lot_id": lot.id,
                })
                continue

            if move.move_line_ids:
                remaining = qty
                for ml in move.move_line_ids:
                    if remaining <= 0:
                        break
                    ml.quantity = remaining
                    remaining = 0.0
            else:
                self.env["stock.move.line"].create({
                    "move_id": move.id,
                    "picking_id": picking.id,
                    "product_id": move.product_id.id,
                    "product_uom_id": move.product_uom.id,
                    "quantity": qty,
                    "location_id": move.location_id.id,
                    "location_dest_id": move.location_dest_id.id,
                })
