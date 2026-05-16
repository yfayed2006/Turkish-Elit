from odoo import _, api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    route_visit_id = fields.Many2one(
        "route.visit",
        string="Route Visit",
        index=True,
        ondelete="set null",
        help="Route visit linked to this stock move.",
    )

    route_visit_line_id = fields.Many2one(
        "route.visit.line",
        string="Route Visit Line",
        index=True,
        ondelete="set null",
        help="Visit line that generated this stock move.",
    )


    route_direct_return_line_id = fields.Many2one(
        "route.direct.return.line",
        string="Direct Return Line",
        index=True,
        ondelete="set null",
        help="Direct return line that generated this stock move.",
    )

    route_product_barcode = fields.Char(
        string="Barcode",
        related="product_id.barcode",
        store=False,
        readonly=True,
    )
    route_product_image_128 = fields.Image(
        string="Image",
        related="product_id.image_128",
        store=False,
        readonly=True,
    )
    route_move_lot_label = fields.Char(
        string="Lot/Serial",
        compute="_compute_route_move_card_info",
        store=False,
        readonly=True,
    )
    route_move_expiry_date = fields.Date(
        string="Expiry Date",
        compute="_compute_route_move_card_info",
        store=False,
        readonly=True,
    )
    route_move_return_route_display = fields.Char(
        string="Route / Reason",
        compute="_compute_route_move_card_info",
        store=False,
        readonly=True,
    )

    route_currency_id = fields.Many2one(
        "res.currency",
        string="Route Currency",
        related="company_id.currency_id",
        store=False,
        readonly=True,
    )

    route_direct_return_unit_price = fields.Monetary(
        string="Unit Price",
        currency_field="route_currency_id",
        copy=False,
        help="Estimated direct return unit price used for settlement visibility.",
    )

    route_direct_return_estimated_amount = fields.Monetary(
        string="Estimated Amount",
        currency_field="route_currency_id",
        copy=False,
        help="Estimated direct return line amount used for settlement visibility.",
    )

    route_move_unit_price_display = fields.Monetary(
        string="Unit Price",
        currency_field="route_currency_id",
        compute="_compute_route_move_card_info",
        store=False,
        readonly=True,
    )
    route_move_value_display = fields.Monetary(
        string="Value",
        currency_field="route_currency_id",
        compute="_compute_route_move_card_info",
        store=False,
        readonly=True,
    )

    @api.depends(
        "move_line_ids.lot_id",
        "move_line_ids.lot_id.expiration_date",
        "route_visit_line_id.lot_id",
        "route_visit_line_id.lot_id.expiration_date",
        "route_visit_line_id.expiry_date",
        "route_visit_line_id.return_qty",
        "route_visit_line_id.return_route",
        "route_direct_return_line_id.lot_id",
        "route_direct_return_line_id.lot_id.expiration_date",
        "route_direct_return_line_id.lot_name",
        "route_direct_return_line_id.expiry_date",
        "route_direct_return_line_id.return_reason_label",
        "route_direct_return_unit_price",
        "route_direct_return_estimated_amount",
        "product_uom_qty",
        "quantity",
    )
    def _compute_route_move_card_info(self):
        route_selection = dict(self.env["route.visit.line"]._fields["return_route"].selection)
        for move in self:
            move_sudo = move.sudo()
            lot_names = []
            expiry_date = False

            visit_line = move_sudo.route_visit_line_id
            direct_return_line = move_sudo.route_direct_return_line_id

            lots = move_sudo.move_line_ids.sudo().mapped("lot_id")
            if visit_line and visit_line.lot_id:
                lots |= visit_line.lot_id.sudo()
            if direct_return_line and direct_return_line.lot_id:
                lots |= direct_return_line.lot_id.sudo()

            for lot in lots:
                if lot and lot.display_name not in lot_names:
                    lot_names.append(lot.display_name)
                if not expiry_date and getattr(lot, "expiration_date", False):
                    expiry_date = fields.Date.to_date(lot.expiration_date)

            if not lot_names and direct_return_line and getattr(direct_return_line, "lot_name", False):
                lot_names.append(direct_return_line.lot_name)

            if not expiry_date and visit_line and getattr(visit_line, "expiry_date", False):
                expiry_date = visit_line.expiry_date
            if not expiry_date and direct_return_line and getattr(direct_return_line, "expiry_date", False):
                expiry_date = direct_return_line.expiry_date

            route_label = False
            if visit_line and (visit_line.return_qty or 0.0) > 0:
                route_label = route_selection.get(visit_line.return_route or "vehicle", visit_line.return_route or "vehicle")
            elif visit_line:
                route_label = _("Refill To Outlet")
            if not route_label and direct_return_line and getattr(direct_return_line, "return_reason_label", False):
                route_label = direct_return_line.return_reason_label

            unit_price = move.route_direct_return_unit_price or 0.0
            if not unit_price and visit_line:
                unit_price = visit_line.unit_price or visit_line.product_id.lst_price or 0.0
            amount = move.route_direct_return_estimated_amount or 0.0
            if not amount:
                qty = move.quantity or move.product_uom_qty or 0.0
                amount = qty * unit_price

            move.route_move_lot_label = ", ".join(lot_names) if lot_names else False
            move.route_move_expiry_date = expiry_date
            move.route_move_return_route_display = route_label
            move.route_move_unit_price_display = unit_price
            move.route_move_value_display = amount
