from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _inherit = "route.visit"

    sale_delivery_count = fields.Integer(
        string="Sales Delivery Count",
        compute="_compute_visit_document_links",
        store=False,
    )
    return_transfer_count = fields.Integer(
        string="Linked Return Transfers",
        compute="_compute_visit_document_links",
        store=False,
    )
    sale_delivery_id = fields.Many2one(
        "stock.picking",
        string="Sales Delivery",
        compute="_compute_visit_document_links",
        store=False,
    )
    generated_shortage_id = fields.Many2one(
        "route.shortage",
        string="Generated Shortage",
        compute="_compute_visit_document_links",
        store=False,
    )

    @api.depends(
        "sale_order_id",
        "return_picking_ids",
        "return_picking_ids.state",
        "return_picking_ids.picking_type_id",
        "return_picking_ids.location_id",
        "refill_picking_id",
        "outlet_id",
    )
    def _compute_visit_document_links(self):
        Picking = self.env["stock.picking"]
        Shortage = self.env["route.shortage"]
        for rec in self:
            rec.sale_delivery_count = 0
            rec.return_transfer_count = 0
            rec.sale_delivery_id = False
            rec.generated_shortage_id = False

            if rec.id:
                sale_deliveries = Picking.search(
                    rec._get_sale_delivery_domain(),
                    order="id desc",
                    limit=1,
                )
                rec.sale_delivery_id = sale_deliveries[:1].id if sale_deliveries else False
                rec.sale_delivery_count = Picking.search_count(rec._get_sale_delivery_domain())

                return_transfers = Picking.search_count(rec._get_return_transfer_domain())
                rec.return_transfer_count = return_transfers

                shortage = Shortage.search(
                    rec._get_generated_shortage_domain(),
                    order="id desc",
                    limit=1,
                )
                rec.generated_shortage_id = shortage[:1].id if shortage else False

    def _get_sale_delivery_domain(self):
        self.ensure_one()
        domain = [
            ("route_visit_id", "=", self.id),
            ("state", "!=", "cancel"),
            ("picking_type_id.code", "=", "outgoing"),
        ]
        if self.sale_order_id:
            domain.append(("origin", "=", self.sale_order_id.name))
        if self.outlet_id and getattr(self.outlet_id, "stock_location_id", False):
            domain.append(("location_id", "=", self.outlet_id.stock_location_id.id))
        return domain

    def _get_return_transfer_domain(self):
        self.ensure_one()
        domain = [
            ("route_visit_id", "=", self.id),
            ("state", "!=", "cancel"),
            ("picking_type_id.code", "=", "internal"),
        ]
        if self.outlet_id and getattr(self.outlet_id, "stock_location_id", False):
            domain.append(("location_id", "=", self.outlet_id.stock_location_id.id))
        if self.refill_picking_id:
            domain.append(("id", "!=", self.refill_picking_id.id))
        if self.sale_order_id:
            domain.append(("origin", "!=", self.sale_order_id.name))
        return domain

    def _get_generated_shortage_domain(self):
        self.ensure_one()
        return [("source_visit_id", "=", self.id)]

    def _get_pickings_action(self, pickings, action_name):
        self.ensure_one()
        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        action["name"] = action_name
        action["domain"] = [("id", "in", pickings.ids)]
        action["context"] = dict(self.env.context, default_route_visit_id=self.id)
        if len(pickings) == 1:
            action["res_id"] = pickings.id
            action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]
        return action

    def action_view_sale_deliveries(self):
        self.ensure_one()
        deliveries = self.env["stock.picking"].search(
            self._get_sale_delivery_domain(),
            order="id desc",
        )
        if not deliveries:
            raise UserError(_("There are no sales deliveries linked to this visit."))
        return self._get_pickings_action(deliveries, _("Sales Delivery"))

    def action_view_return_transfers(self):
        self.ensure_one()
        transfers = self.env["stock.picking"].search(
            self._get_return_transfer_domain(),
            order="id desc",
        )
        if not transfers:
            raise UserError(_("There are no return transfers linked to this visit."))
        return self._get_pickings_action(transfers, _("Return Transfers"))

    def action_view_shortages(self):
        self.ensure_one()
        shortages = self.env["route.shortage"].search(
            self._get_generated_shortage_domain(),
            order="id desc",
        )
        if not shortages:
            raise UserError(_("There are no generated shortages linked to this visit."))

        action = self.env.ref("route_core.action_route_shortage").read()[0]
        action["name"] = _("Generated Shortage")
        action["domain"] = [("id", "in", shortages.ids)]
        action["context"] = dict(
            self.env.context,
            default_source_visit_id=self.id,
            default_outlet_id=self.outlet_id.id if self.outlet_id else False,
        )
        if len(shortages) == 1:
            action["res_id"] = shortages.id
            action["views"] = [(self.env.ref("route_core.view_route_shortage_form").id, "form")]
        return action
