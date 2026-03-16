from odoo import models, _
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _inherit = "route.visit"

    def _get_supply_lines_for_stock_transfer(self):
        self.ensure_one()
        return self.env["route.visit.line"].search(
            [
                ("visit_id", "=", self.id),
                ("supplied_qty", ">", 0),
            ],
            order="id asc",
        )

    def _check_supply_lines_ready_for_stock_transfer(self, lines):
        self.ensure_one()

        if not lines:
            raise UserError(
                _(
                    "There are no visit lines with Supplied Qty greater than zero for visit '%s'."
                )
                % (self.display_name,)
            )

        for line in lines:
            if not line.product_id:
                raise UserError(
                    _("A visit line is missing Product on visit '%s'.")
                    % (self.display_name,)
                )

            if not line.uom_id:
                raise UserError(
                    _(
                        "Product '%s' does not have a Unit of Measure on visit '%s'."
                    )
                    % (line.product_id.display_name, self.display_name)
                )

            if line.supplied_qty <= 0:
                raise UserError(
                    _(
                        "Supplied Qty must be greater than zero for product '%s'."
                    )
                    % (line.product_id.display_name,)
                )

    def _prepare_route_move_vals(self, picking, line):
        self.ensure_one()

        return {
            "name": line.product_id.display_name or line.product_id.name,
            "picking_id": picking.id,
            "company_id": picking.company_id.id,
            "product_id": line.product_id.id,
            "product_uom_qty": line.supplied_qty,
            "product_uom": line.uom_id.id,
            "location_id": picking.location_id.id,
            "location_dest_id": picking.location_dest_id.id,
            "route_visit_id": self.id,
            "route_visit_line_id": line.id,
            "origin": picking.origin or self.name or self.display_name,
        }

    def _create_route_supply_moves(self, picking=None):
        self.ensure_one()

        self._check_route_stock_locations_ready()

        picking = picking or self._create_route_internal_picking()
        lines = self._get_supply_lines_for_stock_transfer()
        self._check_supply_lines_ready_for_stock_transfer(lines)

        StockMove = self.env["stock.move"]
        created_moves = self.env["stock.move"]

        for line in lines:
            existing_move = StockMove.search(
                [
                    ("picking_id", "=", picking.id),
                    ("route_visit_line_id", "=", line.id),
                    ("state", "!=", "cancel"),
                ],
                limit=1,
            )
            if existing_move:
                created_moves |= existing_move
                continue

            vals = self._prepare_route_move_vals(picking, line)
            created_moves |= StockMove.create(vals)

        return created_moves

    def _create_route_internal_picking_with_moves(self):
        self.ensure_one()

        picking = self._create_route_internal_picking()
        self._create_route_supply_moves(picking=picking)
        return picking
