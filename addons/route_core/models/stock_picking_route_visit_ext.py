import html

from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    route_visit_id = fields.Many2one(
        "route.visit",
        string="Route Visit",
        index=True,
        copy=False,
        ondelete="set null",
    )
    route_pda_currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=False,
        readonly=True,
    )
    route_pda_return_line_count = fields.Integer(
        string="Lines",
        compute="_compute_route_pda_return_summary",
        store=False,
    )
    route_pda_return_qty = fields.Float(
        string="Returned Qty",
        compute="_compute_route_pda_return_summary",
        store=False,
    )
    route_pda_return_value = fields.Monetary(
        string="Estimated Value",
        currency_field="route_pda_currency_id",
        compute="_compute_route_pda_return_summary",
        store=False,
    )
    route_pda_move_lines_html = fields.Html(
        string="Product Cards",
        compute="_compute_route_pda_move_lines_html",
        sanitize=False,
        store=False,
        help="Read-only Route/PDA stock movement cards. This avoids switching between list and kanban when screen size changes.",
    )

    @api.depends(
        "move_ids.product_uom_qty",
        "move_ids.quantity",
        "move_ids.route_direct_return_estimated_amount",
        "move_ids.product_id.lst_price",
    )
    def _compute_route_pda_return_summary(self):
        for picking in self:
            moves = picking.move_ids
            line_count = 0
            total_qty = 0.0
            total_value = 0.0
            for move in moves:
                line_count += 1
                qty = (getattr(move, "quantity", 0.0) or 0.0) or (move.product_uom_qty or 0.0)
                total_qty += qty
                amount = getattr(move, "route_direct_return_estimated_amount", 0.0) or 0.0
                if not amount and move.product_id:
                    amount = qty * (move.product_id.lst_price or 0.0)
                total_value += amount
            picking.route_pda_return_line_count = line_count
            picking.route_pda_return_qty = total_qty
            picking.route_pda_return_value = total_value


    def _route_pda_html_escape(self, value):
        return html.escape(str(value or ""), quote=True)

    def _route_pda_format_qty(self, value):
        value = value or 0.0
        return "%.2f" % value

    def _route_pda_format_money(self, amount, currency=False):
        amount = amount or 0.0
        symbol = currency.symbol if currency else ""
        if currency and currency.position == "before":
            return "%s %.2f" % (symbol, amount)
        if symbol:
            return "%.2f %s" % (amount, symbol)
        return "%.2f" % amount

    def _route_pda_format_date_label(self, value):
        if not value:
            return False
        try:
            if hasattr(value, "strftime"):
                return value.strftime("%b %d")
        except Exception:
            pass
        return str(value)

    @api.depends(
        "move_ids.product_id",
        "move_ids.product_id.barcode",
        "move_ids.product_id.image_128",
        "move_ids.product_uom_qty",
        "move_ids.quantity",
        "move_ids.product_uom",
        "move_ids.route_move_lot_label",
        "move_ids.route_move_expiry_date",
        "move_ids.route_move_return_route_display",
        "move_ids.route_move_unit_price_display",
        "move_ids.route_move_value_display",
    )
    def _compute_route_pda_move_lines_html(self):
        for picking in self:
            currency = picking.company_id.currency_id
            cards = []
            moves = picking.move_ids.filtered(lambda move: move.product_id)
            for move in moves:
                product = move.product_id
                image_url = "/web/image/product.product/%s/image_128" % product.id
                product_name = self._route_pda_html_escape(product.display_name or move.display_name)
                barcode = self._route_pda_html_escape(product.barcode or "")
                lot_label = self._route_pda_html_escape(move.route_move_lot_label or "")
                expiry_label = self._route_pda_html_escape(self._route_pda_format_date_label(move.route_move_expiry_date) or "")
                route_label = self._route_pda_html_escape(move.route_move_return_route_display or "")
                uom_label = self._route_pda_html_escape(move.product_uom.display_name or product.uom_id.display_name or "")
                demand = self._route_pda_format_qty(move.product_uom_qty)
                done = self._route_pda_format_qty(getattr(move, "quantity", 0.0) or 0.0)
                unit_price = self._route_pda_format_money(move.route_move_unit_price_display, currency)
                value = self._route_pda_format_money(move.route_move_value_display, currency)

                badges = []
                if lot_label:
                    badges.append('<span class="route_pda_document_product_badge">Lot:%s</span>' % lot_label)
                if expiry_label:
                    badges.append('<span class="route_pda_document_product_badge">Expiry:%s</span>' % expiry_label)
                if route_label:
                    badges.append('<span class="route_pda_document_product_badge route_pda_document_route_badge">%s</span>' % route_label)

                cards.append("""
                    <div class="route_pda_document_product_card">
                        <div class="route_pda_document_product_top">
                            <div class="route_pda_document_product_image_box"><img src="%s" alt="" loading="lazy"/></div>
                            <div class="route_pda_document_product_title_box">
                                <div class="route_pda_document_product_title">%s</div>
                                %s
                                <div class="route_pda_document_product_badges">%s</div>
                            </div>
                        </div>
                        <div class="route_pda_document_product_grid">
                            <div class="route_pda_document_product_metric"><span>Demand</span><strong>%s</strong></div>
                            <div class="route_pda_document_product_metric"><span>Done</span><strong>%s</strong></div>
                            <div class="route_pda_document_product_metric"><span>UoM</span><strong>%s</strong></div>
                            <div class="route_pda_document_product_metric"><span>Movement Route</span><strong>%s</strong></div>
                            <div class="route_pda_document_product_metric"><span>Unit Price</span><strong>%s</strong></div>
                            <div class="route_pda_document_product_metric route_pda_document_product_metric_total"><span>Value</span><strong>%s</strong></div>
                        </div>
                    </div>
                """ % (
                    image_url,
                    product_name,
                    ('<div class="route_pda_document_product_subtitle">Barcode: %s</div>' % barcode) if barcode else "",
                    "".join(badges),
                    demand,
                    done,
                    uom_label,
                    route_label,
                    unit_price,
                    value,
                ))

            if cards:
                picking.route_pda_move_lines_html = '<div class="route_pda_document_product_cards_html">%s</div>' % "".join(cards)
            else:
                picking.route_pda_move_lines_html = '<div class="route_pda_document_product_cards_html"><div class="route_pda_document_product_card"><div class="route_pda_document_product_title">No product lines.</div></div></div>'

    def _get_related_consignment_outlets_for_balance_sync(self):
        self.ensure_one()
        outlet_model = self.env["route.outlet"].sudo()
        locations = (self.location_id | self.location_dest_id).filtered(lambda loc: loc)
        if not locations:
            return outlet_model.browse()
        return outlet_model.search([
            ("outlet_operation_mode", "=", "consignment"),
            ("stock_location_id", "child_of", locations.ids),
        ])

    def _sync_related_consignment_outlet_balances(self):
        outlet_model = self.env["route.outlet"].sudo()
        outlets = outlet_model.browse()
        for picking in self.filtered(lambda p: p.state == "done" and getattr(p.picking_type_id, "code", False) == "internal"):
            outlets |= picking._get_related_consignment_outlets_for_balance_sync()
        if outlets:
            outlets._sync_outlet_stock_balance_records()
        return True

    def action_back_to_outlet_form(self):
        self.ensure_one()
        outlet = False
        outlet_id = self.env.context.get("route_outlet_back_id") or self.env.context.get("default_outlet_id")
        if outlet_id:
            outlet = self.env["route.outlet"].browse(outlet_id).exists()
        if not outlet and getattr(self, "route_direct_return_id", False) and self.route_direct_return_id.outlet_id:
            outlet = self.route_direct_return_id.outlet_id
        if not outlet and getattr(self, "route_visit_id", False) and self.route_visit_id.outlet_id:
            outlet = self.route_visit_id.outlet_id
        if outlet:
            return outlet.action_open_pda_form()
        home = self.env["route.pda.home"].create({})
        home._refresh_dashboard_snapshot()
        view = self.env.ref("route_core.view_route_pda_outlet_center_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": "Customer Profiles",
            "res_model": "route.pda.home",
            "res_id": home.id,
            "view_mode": "form",
            "target": "main",
            "context": {"create": 0, "edit": 0, "delete": 0},
        }
        if view:
            action["views"] = [(view.id, "form")]
        return action

    def action_back_to_visit_or_outlet_form(self):
        self.ensure_one()

        visit = self.env["route.visit"].browse()
        visit_id = (
            self.env.context.get("route_visit_back_id")
            or self.env.context.get("route_visit_id")
            or self.env.context.get("default_route_visit_id")
        )
        if visit_id:
            visit = self.env["route.visit"].browse(visit_id).exists()

        if not visit and self.route_visit_id:
            visit = self.route_visit_id.exists()

        if not visit and self.origin:
            visit = self.env["route.visit"].search([("name", "=", self.origin)], limit=1)

        if visit:
            if hasattr(visit, "_get_pda_form_action"):
                return visit.with_context(
                    pda_mode=True,
                    route_pda_salesperson_mode=True,
                )._get_pda_form_action()

            pda_view = self.env.ref("route_core.view_route_visit_pda_form", raise_if_not_found=False)
            fallback_view = self.env.ref("route_core.view_route_visit_form", raise_if_not_found=False)
            form_view = pda_view or fallback_view
            action = {
                "type": "ir.actions.act_window",
                "name": visit.display_name,
                "res_model": "route.visit",
                "res_id": visit.id,
                "view_mode": "form",
                "target": "current",
                "context": dict(
                    self.env.context,
                    create=False,
                    edit=True,
                    delete=False,
                    pda_mode=True,
                    route_pda_salesperson_mode=True,
                ),
            }
            if form_view:
                action["views"] = [(form_view.id, "form")]
            return action

        return self.action_back_to_outlet_form()

    def _get_route_visit_finish_return_action(self):
        self.ensure_one()
        if not self.env.context.get("route_return_to_finish_summary"):
            return False

        visit = self.route_visit_id.exists() or self.env["route.visit"].browse(self.env.context.get("route_visit_id")).exists()
        if not visit:
            return False

        if visit.state == "in_progress":
            finish_result = visit.action_end_visit()
            if isinstance(finish_result, dict):
                return finish_result

        if visit.state == "done" and hasattr(visit, "_get_route_visit_finish_summary_action"):
            return visit._get_route_visit_finish_summary_action()

        if hasattr(visit, "_get_pda_form_action"):
            return visit._get_pda_form_action()
        return False

    def _post_validate_route_visit_action(self):
        done_pickings = self.filtered(lambda p: p.state == "done")
        done_pickings._sync_related_consignment_outlet_balances()
        for picking in done_pickings:
            action = picking._get_route_visit_finish_return_action()
            if action:
                return action
        return False

    def button_validate(self):
        result = super().button_validate()
        followup_action = self._post_validate_route_visit_action()
        return followup_action or result

    def action_done(self):
        result = super().action_done()
        followup_action = self._post_validate_route_visit_action()
        return followup_action or result
