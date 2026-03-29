from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _inherit = "route.visit"

    refill_picking_id = fields.Many2one(
        "stock.picking",
        string="Refill Transfer",
        readonly=True,
        copy=False,
        tracking=True,
    )

    refill_picking_count = fields.Integer(
        string="Refill Transfer Count",
        compute="_compute_refill_picking_count",
        store=False,
    )

    refill_credit_warning_visible = fields.Boolean(
        string="Refill Credit Warning Visible",
        compute="_compute_refill_credit_warning",
        store=False,
    )

    refill_credit_warning_html = fields.Html(
        string="Refill Credit Warning",
        compute="_compute_refill_credit_warning",
        sanitize=False,
        store=False,
    )

    def _compute_refill_picking_count(self):
        for rec in self:
            rec.refill_picking_count = 1 if rec.refill_picking_id else 0

    @api.depends(
        "outlet_id",
        "outlet_id.shelf_credit_limit_amount",
        "outlet_id.stock_total_value",
        "line_ids.supplied_qty",
        "line_ids.unit_price",
        "visit_process_state",
    )
    def _compute_refill_credit_warning(self):
        for rec in self:
            rec.refill_credit_warning_visible = False
            rec.refill_credit_warning_html = False

            outlet = rec.outlet_id
            if not outlet:
                continue

            limit_amount = outlet.shelf_credit_limit_amount or 0.0
            current_shelf_value = outlet.stock_total_value or 0.0
            refill_value = rec._get_refill_total_value()
            projected_shelf_value = current_shelf_value + refill_value
            available_capacity = max(limit_amount - current_shelf_value, 0.0)
            over_limit_by = max(projected_shelf_value - limit_amount, 0.0)

            if limit_amount <= 0:
                continue

            if projected_shelf_value > limit_amount and refill_value > 0:
                rec.refill_credit_warning_visible = True
                rec.refill_credit_warning_html = _(
                    "<div class='alert alert-danger mb-3' role='alert'>"
                    "<strong>Refill warning:</strong> Outlet shelf credit limit will be exceeded."
                    "<br/>Outlet: %(outlet)s"
                    "<br/>Current shelf value: %(current).2f"
                    "<br/>Refill value: %(refill).2f"
                    "<br/>Projected shelf value: %(projected).2f"
                    "<br/>Shelf credit limit: %(limit).2f"
                    "<br/>Available capacity before refill: %(available).2f"
                    "<br/>Over limit by: %(over).2f"
                    "</div>"
                ) % {
                    "outlet": outlet.display_name,
                    "current": current_shelf_value,
                    "refill": refill_value,
                    "projected": projected_shelf_value,
                    "limit": limit_amount,
                    "available": available_capacity,
                    "over": over_limit_by,
                }
            elif current_shelf_value > limit_amount:
                rec.refill_credit_warning_visible = True
                rec.refill_credit_warning_html = _(
                    "<div class='alert alert-warning mb-3' role='alert'>"
                    "<strong>Outlet already over shelf credit limit.</strong>"
                    "<br/>Outlet: %(outlet)s"
                    "<br/>Current shelf value: %(current).2f"
                    "<br/>Shelf credit limit: %(limit).2f"
                    "<br/>Over limit by: %(over).2f"
                    "</div>"
                ) % {
                    "outlet": outlet.display_name,
                    "current": current_shelf_value,
                    "limit": limit_amount,
                    "over": max(current_shelf_value - limit_amount, 0.0),
                }

    def _get_refill_transfer_lines(self):
        self.ensure_one()
        return self.line_ids.filtered(
            lambda line: line.product_id and (line.supplied_qty or 0.0) > 0
        )

    def _prepare_refill_picking_vals(self):
        self.ensure_one()
        picking_type = self._get_internal_picking_type()
        source_location = self._get_vehicle_stock_location()
        dest_location = self._get_outlet_stock_location()
        return {
            "picking_type_id": picking_type.id,
            "location_id": source_location.id,
            "location_dest_id": dest_location.id,
            "origin": self.name,
            "route_visit_id": self.id,
            "partner_id": self.partner_id.id if self.partner_id else False,
            "move_type": "direct",
        }

    def _prepare_refill_move_vals(self, picking, line):
        self.ensure_one()
        return {
            "product_id": line.product_id.id,
            "product_uom_qty": line.supplied_qty,
            "product_uom": line.uom_id.id or line.product_id.uom_id.id,
            "location_id": picking.location_id.id,
            "location_dest_id": picking.location_dest_id.id,
            "picking_id": picking.id,
            "route_visit_id": self.id,
        }

    def _fill_move_line_qty_done(self, picking):
        for move in picking.move_ids:
            qty = move.product_uom_qty or 0.0
            if qty <= 0:
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

    def _get_refill_total_value(self):
        self.ensure_one()
        return sum(
            (line.supplied_qty or 0.0) * (line.unit_price or 0.0)
            for line in self._get_refill_transfer_lines()
        )

    def _check_outlet_shelf_credit_limit(self):
        self.ensure_one()
        outlet = self.outlet_id
        limit_amount = outlet.shelf_credit_limit_amount or 0.0
        if limit_amount <= 0:
            return

        current_shelf_value = outlet.stock_total_value or 0.0
        refill_value = self._get_refill_total_value()
        projected_shelf_value = current_shelf_value + refill_value

        if projected_shelf_value > limit_amount:
            raise UserError(
                _(
                    "Outlet shelf credit limit exceeded.\n\n"
                    "Outlet: %s\n"
                    "Current shelf value: %.2f\n"
                    "Refill value: %.2f\n"
                    "Projected shelf value: %.2f\n"
                    "Shelf credit limit: %.2f\n"
                    "Available capacity before refill: %.2f"
                )
                % (
                    outlet.display_name,
                    current_shelf_value,
                    refill_value,
                    projected_shelf_value,
                    limit_amount,
                    max(limit_amount - current_shelf_value, 0.0),
                )
            )

    def _create_refill_picking(self):
        self.ensure_one()

        if self.refill_picking_id and self.refill_picking_id.state != "cancel":
            return self.refill_picking_id

        if self.state != "in_progress":
            raise UserError(_("Refill transfer can only be created while the visit is in progress."))

        if self.visit_process_state != "reconciled":
            raise UserError(_("Refill transfer can only be created after reconciliation."))

        self._check_route_stock_locations_ready()

        lines = self._get_refill_transfer_lines()
        if not lines:
            raise UserError(_("There are no refill quantities to transfer."))

        self._check_outlet_shelf_credit_limit()

        picking_vals = self._prepare_refill_picking_vals()
        picking = self.env["stock.picking"].create(picking_vals)

        for line in lines:
            move_vals = self._prepare_refill_move_vals(picking, line)
            self.env["stock.move"].create(move_vals)

        self.refill_picking_id = picking.id
        return picking

    def action_confirm_refill_transfer(self):
        self.ensure_one()

        picking = self._create_refill_picking()

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
                _("The refill transfer was created, but it could not be fully validated automatically.")
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Visit"),
            "res_model": "route.visit",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_refill_transfer(self):
        self.ensure_one()

        if not self.refill_picking_id:
            raise UserError(_("There is no refill transfer linked to this visit."))

        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        action["res_id"] = self.refill_picking_id.id
        action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]
        action["context"] = {
            "default_route_visit_id": self.id,
        }
        return action
