from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _fill_move_line_qty_done(self, picking):
        visit = getattr(picking, "route_visit_id", False)
        for move in picking.move_ids:
            qty = move.product_uom_qty or 0.0
            if qty <= 0:
                continue

            line = False
            if visit:
                line = move.route_visit_line_id or visit.line_ids.filtered(lambda l: l.product_id == move.product_id)[:1]

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
                for move_line in move.move_line_ids:
                    if remaining <= 0:
                        break
                    move_line.quantity = remaining
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
