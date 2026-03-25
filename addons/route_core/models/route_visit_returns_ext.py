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
        if hasattr(self, "_get_pda_form_action"):
            return self._get_pda_form_action()
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
            "name": _("Scan Returns"),
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
                _("No Returns can only be confirmed during the counting stage.")
            )

        self.write({
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

    def _get_return_transfer_lines(self):
        self.ensure_one()
        return self.line_ids.filtered(
            lambda line: line.product_id and (line.return_qty or 0.0) > 0
        )

    def _get_return_destination_location(self, return_route):
        self.ensure_one()

        if return_route == "vehicle":
            return self._get_vehicle_stock_location()

        company = self.company_id or self.env.company

        if return_route == "damaged":
            location = company.return_damaged_location_id
            if not location:
                raise UserError(
                    _(
                        "Please configure Return Damaged Location in route return settings before confirming damaged returns."
                    )
                )
            return location

        if return_route == "near_expiry":
            location = company.return_near_expiry_location_id
            if not location:
                raise UserError(
                    _(
                        "Please configure Return Near Expiry Location in route return settings before confirming near expiry returns."
                    )
                )
            return location

        raise UserError(_("Invalid return route."))

    def _prepare_return_picking_vals(self, destination_location, return_route):
        self.ensure_one()
        picking_type = self._get_internal_picking_type()
        source_location = self._get_outlet_stock_location()

        route_label_map = {
            "vehicle": _("To Vehicle"),
            "damaged": _("To Damaged Stock"),
            "near_expiry": _("To Near Expiry Stock"),
        }

        return {
            "picking_type_id": picking_type.id,
            "location_id": source_location.id,
            "location_dest_id": destination_location.id,
            "origin": "%s - %s" % (
                self.name,
                route_label_map.get(return_route, return_route),
            ),
            "route_visit_id": self.id,
            "partner_id": self.partner_id.id if self.partner_id else False,
            "move_type": "direct",
            "company_id": (self.company_id or self.env.company).id,
        }

    def _prepare_return_move_vals(self, picking, line):
        self.ensure_one()
        return {
            "product_id": line.product_id.id,
            "product_uom_qty": line.return_qty,
            "product_uom": line.uom_id.id or line.product_id.uom_id.id,
            "location_id": picking.location_id.id,
            "location_dest_id": picking.location_dest_id.id,
            "picking_id": picking.id,
            "route_visit_id": self.id,
            "route_visit_line_id": line.id,
            "origin": picking.origin or self.name or self.display_name,
        }

    def _create_return_pickings(self):
        self.ensure_one()

        if self.state != "in_progress":
            raise UserError(
                _("Return transfers can only be created while the visit is in progress.")
            )

        if self.visit_process_state != "reconciled":
            raise UserError(
                _("Return transfers can only be created after reconciliation.")
            )

        self._check_route_stock_locations_ready()

        lines = self._get_return_transfer_lines()
        if not lines:
            raise UserError(_("There are no return quantities to transfer."))

        created_pickings = self.env["stock.picking"]
        StockPicking = self.env["stock.picking"]
        StockMove = self.env["stock.move"]

        for return_route in ("vehicle", "damaged", "near_expiry"):
            route_lines = lines.filtered(
                lambda l, rr=return_route: (l.return_route or "vehicle") == rr
            )
            if not route_lines:
                continue

            destination_location = self._get_return_destination_location(return_route)
            source_location = self._get_outlet_stock_location()

            picking = StockPicking.search(
                [
                    ("route_visit_id", "=", self.id),
                    ("location_id", "=", source_location.id),
                    ("location_dest_id", "=", destination_location.id),
                    ("state", "!=", "cancel"),
                ],
                limit=1,
            )

            if not picking:
                picking_vals = self._prepare_return_picking_vals(
                    destination_location,
                    return_route,
                )
                picking = StockPicking.create(picking_vals)

            for line in route_lines:
                existing_move = StockMove.search(
                    [
                        ("picking_id", "=", picking.id),
                        ("route_visit_line_id", "=", line.id),
                        ("state", "!=", "cancel"),
                    ],
                    limit=1,
                )
                if existing_move:
                    continue

                move_vals = self._prepare_return_move_vals(picking, line)
                StockMove.create(move_vals)

            created_pickings |= picking

        if not created_pickings:
            raise UserError(_("No return transfers were created."))

        return created_pickings

    def action_confirm_return_transfers(self):
        self.ensure_one()

        pickings = self._create_return_pickings()

        for picking in pickings:
            if picking.state == "draft":
                picking.action_confirm()

            if picking.state in ("confirmed", "waiting"):
                picking.action_assign()

            self._fill_move_line_qty_done(picking)

            if picking.state not in ("done", "cancel"):
                result = picking.button_validate()
                if isinstance(result, dict):
                    return result

            if picking.state != "done":
                raise UserError(
                    _(
                        "The return transfer was created, but it could not be fully validated automatically."
                    )
                )

        self.write({
            "returns_step_done": True,
            "has_returns_declared": bool(self._get_return_transfer_lines()),
        })

        return self._action_reopen_visit_form()

    def action_view_return_transfers(self):
        self.ensure_one()

        return_pickings = self.return_picking_ids.filtered(
            lambda p: p.location_id == self.outlet_stock_location_id
        )

        if not return_pickings:
            raise UserError(_("There are no return transfers linked to this visit."))

        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        action["domain"] = [("id", "in", return_pickings.ids)]
        action["context"] = {
            "default_route_visit_id": self.id,
            "default_picking_type_id": self._get_internal_picking_type().id,
            "default_location_id": self._get_outlet_stock_location().id,
        }

        if len(return_pickings) == 1:
            action["res_id"] = return_pickings.id
            action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]

        return action
