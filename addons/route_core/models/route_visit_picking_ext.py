from odoo import fields, models, _
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _inherit = "route.visit"

    picking_ids = fields.One2many(
        "stock.picking",
        "route_visit_id",
        string="Stock Pickings",
    )

    picking_count = fields.Integer(
        string="Stock Pickings Count",
        compute="_compute_picking_count",
        store=False,
    )

    def _compute_picking_count(self):
        for rec in self:
            rec.picking_count = len(rec.picking_ids)

    def _get_internal_picking_type(self):
        self.ensure_one()

        company = self.company_id or self.env.company

        picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", "internal"),
                "|",
                ("company_id", "=", company.id),
                ("company_id", "=", False),
            ],
            order="company_id desc, sequence asc, id asc",
            limit=1,
        )

        if not picking_type:
            raise UserError(
                _(
                    "No Internal Transfer Operation Type was found for company '%s'."
                )
                % (company.display_name,)
            )

        return picking_type

    def _prepare_route_internal_picking_vals(self):
        self.ensure_one()

        self._check_route_stock_locations_ready()

        locations = self._get_route_stock_locations()
        source_location = locations["source_location"]
        destination_location = locations["destination_location"]
        picking_type = self._get_internal_picking_type()

        origin = self.name or self.display_name or _("Route Visit")

        return {
            "picking_type_id": picking_type.id,
            "location_id": source_location.id,
            "location_dest_id": destination_location.id,
            "origin": origin,
            "route_visit_id": self.id,
            "company_id": (self.company_id or self.env.company).id,
            "note": _(
                "Route transfer prepared from vehicle location to outlet location."
            ),
        }

    def _create_route_internal_picking(self):
        self.ensure_one()

        existing = self.picking_ids.filtered(
            lambda p: p.state != "cancel"
            and p.location_id == self.vehicle_stock_location_id
            and p.location_dest_id == self.outlet_stock_location_id
        )[:1]
        if existing:
            return existing

        vals = self._prepare_route_internal_picking_vals()
        return self.env["stock.picking"].create(vals)

    def action_open_pickings(self):
        self.ensure_one()

        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        action["domain"] = [("route_visit_id", "=", self.id)]
        action["context"] = {
            "default_route_visit_id": self.id,
            "default_picking_type_id": self._get_internal_picking_type().id,
            "default_location_id": self._get_vehicle_stock_location().id,
            "default_location_dest_id": self._get_outlet_stock_location().id,
        }

        if self.picking_count == 1:
            action["res_id"] = self.picking_ids[:1].id
            action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]

        return action

    def action_prepare_stock_transfer(self):
        self.ensure_one()

        if self.state != "in_progress":
            raise UserError(
                _("You can only prepare stock transfer when the visit is in progress.")
            )

        picking = self._create_route_internal_picking_with_moves()

        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        action["res_id"] = picking.id
        action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]
        action["context"] = {
            "default_route_visit_id": self.id,
            "default_picking_type_id": picking.picking_type_id.id,
            "default_location_id": picking.location_id.id,
            "default_location_dest_id": picking.location_dest_id.id,
        }
        return action
