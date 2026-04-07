from collections import defaultdict
import math
from datetime import date as pydate
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


_MAX_DATE = pydate(9999, 12, 31)


def _is_discrete_uom(product):
    uom = getattr(product, "uom_id", False)
    if not uom:
        return False
    rounding = getattr(uom, "rounding", 0.0) or 0.0
    name = (getattr(uom, "name", "") or "").strip().lower()
    discrete_names = {"piece", "pieces", "unit", "units", "pc", "pcs", "قطعة"}
    return rounding >= 1.0 or name in discrete_names


def _qty_up(product, qty):
    qty = max(qty or 0.0, 0.0)
    if _is_discrete_uom(product):
        return float(math.ceil(qty - 1e-9))
    return qty


def _qty_down(product, qty):
    qty = max(qty or 0.0, 0.0)
    if _is_discrete_uom(product):
        return float(math.floor(qty + 1e-9))
    return qty


def _lot_priority_date(lot):
    for field_name in ("removal_date", "expiration_date", "life_date", "use_date", "alert_date"):
        value = getattr(lot, field_name, False)
        if value:
            try:
                return fields.Date.to_date(value)
            except Exception:
                return value
    return False


class RouteLoadingProposal(models.Model):
    _name = "route.loading.proposal"
    _description = "Route Vehicle Loading Proposal"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "plan_date desc, id desc"

    name = fields.Char(
        string="Proposal Reference",
        required=True,
        copy=False,
        readonly=True,
        default="New",
        tracking=True,
    )
    plan_id = fields.Many2one(
        "route.plan",
        string="Route Plan",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    plan_date = fields.Date(
        string="Plan Date",
        related="plan_id.date",
        store=True,
        readonly=True,
    )
    planning_finalized = fields.Boolean(
        string="Daily Planning Finalized",
        related="plan_id.planning_finalized",
        readonly=True,
        store=False,
    )
    planning_finalized_datetime = fields.Datetime(
        string="Planning Finalized On",
        related="plan_id.planning_finalized_datetime",
        readonly=True,
        store=False,
    )
    vehicle_id = fields.Many2one(
        "route.vehicle",
        string="Vehicle",
        related="plan_id.vehicle_id",
        store=True,
        readonly=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        related="plan_id.user_id",
        store=True,
        readonly=True,
    )
    source_location_id = fields.Many2one(
        "stock.location",
        string="Source Warehouse Location",
        domain="[('usage', '=', 'internal')]",
        tracking=True,
    )
    destination_location_id = fields.Many2one(
        "stock.location",
        string="Vehicle Location",
        related="vehicle_id.stock_location_id",
        readonly=True,
        store=False,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )
    approval_datetime = fields.Datetime(
        string="Approved On",
        readonly=True,
        copy=False,
        tracking=True,
    )
    picking_id = fields.Many2one(
        "stock.picking",
        string="Internal Transfer",
        readonly=True,
        copy=False,
        tracking=True,
    )
    transfer_state = fields.Selection(
        related="picking_id.state",
        string="Transfer State",
        store=False,
        readonly=True,
    )
    note = fields.Text(string="Notes")
    line_ids = fields.One2many(
        "route.loading.proposal.line",
        "proposal_id",
        string="Proposal Lines",
        copy=True,
    )
    line_count = fields.Integer(
        string="Line Count",
        compute="_compute_totals",
        store=False,
    )
    product_count = fields.Integer(
        string="Product Count",
        compute="_compute_totals",
        store=False,
    )
    planned_outlet_count = fields.Integer(
        string="Planned Outlets",
        compute="_compute_totals",
        store=False,
    )
    total_required_qty = fields.Float(
        string="Total Required Qty",
        compute="_compute_totals",
        store=False,
    )
    total_vehicle_balance_qty = fields.Float(
        string="Vehicle Balance Qty",
        compute="_compute_totals",
        store=False,
    )
    total_suggested_qty = fields.Float(
        string="Suggested Load Qty",
        compute="_compute_totals",
        store=False,
    )
    total_approved_qty = fields.Float(
        string="Approved Qty",
        compute="_compute_totals",
        store=False,
    )
    total_required_value = fields.Monetary(
        string="Required Value",
        currency_field="currency_id",
        compute="_compute_totals",
        store=False,
    )
    total_approved_value = fields.Monetary(
        string="Approved Value",
        currency_field="currency_id",
        compute="_compute_totals",
        store=False,
    )
    transfer_count = fields.Integer(
        string="Transfer Count",
        compute="_compute_transfer_count",
        store=False,
    )

    _sql_constraints = [
        (
            "route_loading_proposal_plan_unique",
            "unique(plan_id)",
            "Only one loading proposal is allowed for each route plan.",
        ),
    ]

    @api.depends(
        "line_ids",
        "line_ids.total_required_qty",
        "line_ids.vehicle_available_qty",
        "line_ids.suggested_load_qty",
        "line_ids.approved_qty",
        "line_ids.required_value",
        "line_ids.approved_value",
    )
    def _compute_totals(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.product_count = len(rec.line_ids.filtered("product_id"))
            rec.planned_outlet_count = len(rec.plan_id.line_ids.filtered("outlet_id")) if rec.plan_id else 0
            rec.total_required_qty = sum(rec.line_ids.mapped("total_required_qty"))
            rec.total_vehicle_balance_qty = sum(rec.line_ids.mapped("vehicle_available_qty"))
            rec.total_suggested_qty = sum(rec.line_ids.mapped("suggested_load_qty"))
            rec.total_approved_qty = sum(rec.line_ids.mapped("approved_qty"))
            rec.total_required_value = sum(rec.line_ids.mapped("required_value"))
            rec.total_approved_value = sum(rec.line_ids.mapped("approved_value"))

    def _compute_transfer_count(self):
        for rec in self:
            rec.transfer_count = 1 if rec.picking_id else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("route.loading.proposal") or "New"
        return super().create(vals_list)

    def _get_source_warehouse(self, source_location=False):
        self.ensure_one()
        source_location = source_location or self._get_effective_source_location()
        if not source_location:
            return False

        company = self.company_id or self.env.company
        warehouse_model = self.env["stock.warehouse"]
        warehouses = warehouse_model.search(
            [
                "|",
                ("company_id", "=", company.id),
                ("company_id", "=", False),
            ]
        )
        if not warehouses:
            return False

        source_path = (source_location.complete_name or "").strip()
        matches = []
        for warehouse in warehouses:
            root = getattr(warehouse, "lot_stock_id", False)
            if not root:
                continue
            root_path = (root.complete_name or "").strip()
            if not root_path:
                continue
            if source_location.id == root.id or source_path == root_path or source_path.startswith(root_path + "/"):
                matches.append((len(root_path), warehouse.id, warehouse))

        if matches:
            matches.sort(key=lambda item: (-item[0], item[1]))
            return matches[0][2]
        return False

    def _get_internal_picking_type(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        source_location = self._get_effective_source_location()
        warehouse = self._get_source_warehouse(source_location)
        picking_type_model = self.env["stock.picking.type"]

        if warehouse:
            int_type = getattr(warehouse, "int_type_id", False)
            if int_type and getattr(int_type, "code", False) == "internal":
                return int_type

            if "warehouse_id" in picking_type_model._fields:
                picking_type = picking_type_model.search(
                    [
                        ("code", "=", "internal"),
                        ("warehouse_id", "=", warehouse.id),
                        "|",
                        ("company_id", "=", company.id),
                        ("company_id", "=", False),
                    ],
                    order="company_id desc, sequence asc, id asc",
                    limit=1,
                )
                if picking_type:
                    return picking_type

            root_location = getattr(warehouse, "lot_stock_id", False)
            if root_location and "default_location_src_id" in picking_type_model._fields:
                candidate_types = picking_type_model.search(
                    [
                        ("code", "=", "internal"),
                        "|",
                        ("company_id", "=", company.id),
                        ("company_id", "=", False),
                    ],
                    order="company_id desc, sequence asc, id asc",
                )
                root_path = (root_location.complete_name or "").strip()
                for picking_type in candidate_types:
                    default_src = getattr(picking_type, "default_location_src_id", False)
                    default_src_path = (default_src.complete_name or "").strip() if default_src else ""
                    if default_src and (default_src.id == root_location.id or default_src_path == root_path or default_src_path.startswith(root_path + "/")):
                        return picking_type

        picking_type = picking_type_model.search(
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
                _("No Internal Transfer operation type was found for company '%s'.")
                % (company.display_name,)
            )
        return picking_type

    def _get_mus_stock_location(self):
        self.ensure_one()
        location_model = self.env["stock.location"]

        mus_location = location_model.search(
            [
                ("usage", "=", "internal"),
                ("complete_name", "=", "MUS/Stock"),
            ],
            order="id asc",
            limit=1,
        )
        if mus_location:
            return mus_location

        mus_location = location_model.search(
            [
                ("usage", "=", "internal"),
                ("complete_name", "ilike", "MUS/Stock"),
            ],
            order="id asc",
            limit=1,
        )
        if mus_location:
            return mus_location

        mus_location = location_model.search(
            [
                ("usage", "=", "internal"),
                ("name", "=", "Stock"),
                ("complete_name", "ilike", "MUS/%"),
            ],
            order="id asc",
            limit=1,
        )
        if mus_location:
            return mus_location

        mus_location = location_model.search(
            [
                ("usage", "=", "internal"),
                "|",
                ("name", "=", "MUS/Stock"),
                ("name", "ilike", "MUS/Stock"),
            ],
            order="id asc",
            limit=1,
        )
        return mus_location

    def _get_effective_source_location(self):
        self.ensure_one()
        return self.source_location_id or self._get_default_source_location() or False

    def action_open_source_location_wizard(self):
        self.ensure_one()
        default_source = self.source_location_id or self._get_default_source_location()
        return {
            "type": "ir.actions.act_window",
            "name": _("Choose Loading Source"),
            "res_model": "route.loading.source.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_plan_id": self.plan_id.id,
                "default_proposal_id": self.id,
                "default_source_location_id": default_source.id if default_source else False,
            },
        }

    def _get_default_source_location(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        location_model = self.env["stock.location"]

        # Route Core preference: force MUS/Stock as the primary warehouse source whenever it exists.
        preferred_location = self._get_mus_stock_location()
        if preferred_location:
            return preferred_location

        picking_type = self._get_internal_picking_type()
        if (
            "default_location_src_id" in picking_type._fields
            and picking_type.default_location_src_id
            and picking_type.default_location_src_id.usage == "internal"
        ):
            return picking_type.default_location_src_id

        warehouse = self.env["stock.warehouse"].search(
            [
                "|",
                ("company_id", "=", company.id),
                ("company_id", "=", False),
            ],
            order="company_id desc, id asc",
            limit=1,
        )
        if warehouse and warehouse.lot_stock_id:
            return warehouse.lot_stock_id

        return False

    def _get_quant_available_qty(self, quant):
        reserved = 0.0
        if "reserved_quantity" in quant._fields:
            reserved = quant.reserved_quantity or 0.0
        available = (quant.quantity or 0.0) - reserved
        return max(available, 0.0)

    def _lot_sort_key(self, lot):
        lot_date = _lot_priority_date(lot)
        today = fields.Date.context_today(self)
        is_expired = bool(lot_date and lot_date < today)
        return (
            1 if is_expired else 0,
            lot_date or _MAX_DATE,
            lot.name or "",
            lot.id,
        )

    def _prepare_tracked_move_lines(self, move):
        self.ensure_one()
        quantity_needed = move.product_uom_qty or 0.0
        if quantity_needed <= 0 or not move.location_id:
            return []

        domain = [
            ("location_id", "child_of", move.location_id.id),
            ("product_id", "=", move.product_id.id),
            ("quantity", ">", 0),
            ("lot_id", "!=", False),
        ]
        quants = self.env["stock.quant"].search(domain)

        candidate_quants = []
        today = fields.Date.context_today(self)
        for quant in quants:
            available_qty = self._get_quant_available_qty(quant)
            if available_qty <= 0:
                continue
            lot = quant.lot_id
            if not lot:
                continue
            lot_date = _lot_priority_date(lot)
            if lot_date and lot_date < today:
                continue
            candidate_quants.append((self._lot_sort_key(lot), quant, lot, available_qty))

        if not candidate_quants:
            return []

        candidate_quants.sort(key=lambda item: item[0])
        move_line_vals = []
        remaining = quantity_needed

        for _sort_key, _quant, lot, available_qty in candidate_quants:
            if remaining <= 0:
                break

            if move.product_id.tracking == "serial":
                serial_units = int(min(available_qty, remaining))
                for _i in range(serial_units):
                    move_line_vals.append(
                        {
                            "move_id": move.id,
                            "picking_id": move.picking_id.id,
                            "product_id": move.product_id.id,
                            "product_uom_id": move.product_uom.id,
                            "quantity": 1.0,
                            "location_id": move.location_id.id,
                            "location_dest_id": move.location_dest_id.id,
                            "lot_id": lot.id,
                        }
                    )
                    remaining -= 1.0
                    if remaining <= 0:
                        break
                continue

            allocate_qty = min(available_qty, remaining)
            if allocate_qty <= 0:
                continue
            move_line_vals.append(
                {
                    "move_id": move.id,
                    "picking_id": move.picking_id.id,
                    "product_id": move.product_id.id,
                    "product_uom_id": move.product_uom.id,
                    "quantity": allocate_qty,
                    "location_id": move.location_id.id,
                    "location_dest_id": move.location_dest_id.id,
                    "lot_id": lot.id,
                }
            )
            remaining -= allocate_qty

        return move_line_vals

    def _apply_oldest_lot_allocation(self, picking):
        self.ensure_one()
        for move in picking.move_ids:
            qty = move.product_uom_qty or 0.0
            if qty <= 0:
                continue

            tracking = getattr(move.product_id, "tracking", "none") or "none"
            if tracking in ("lot", "serial"):
                tracked_move_lines = self._prepare_tracked_move_lines(move)
                if tracked_move_lines:
                    if move.move_line_ids:
                        move.move_line_ids.unlink()
                    self.env["stock.move.line"].create(tracked_move_lines)
                continue

            if move.move_line_ids:
                remaining = qty
                for move_line in move.move_line_ids:
                    if remaining <= 0:
                        move_line.unlink()
                        continue
                    move_line.quantity = remaining
                    remaining = 0.0
            else:
                self.env["stock.move.line"].create(
                    {
                        "move_id": move.id,
                        "picking_id": picking.id,
                        "product_id": move.product_id.id,
                        "product_uom_id": move.product_uom.id,
                        "quantity": qty,
                        "location_id": move.location_id.id,
                        "location_dest_id": move.location_dest_id.id,
                    }
                )

    def _check_ready_for_approval(self):
        for rec in self:
            if not rec.plan_id:
                raise UserError(_("This loading proposal is not linked to any route plan."))
            if not rec.plan_id.planning_finalized:
                raise UserError(
                    _(
                        "Finalize the vehicle's daily route plan first, then generate or approve the loading proposal."
                    )
                )
            if not rec.vehicle_id:
                raise UserError(_("The linked route plan does not have a vehicle."))
            if not getattr(rec.vehicle_id, "stock_location_id", False):
                raise UserError(
                    _("Vehicle '%s' does not have a vehicle stock location.")
                    % (rec.vehicle_id.display_name,)
                )
            effective_source = rec._get_effective_source_location()
            if not effective_source:
                raise UserError(
                    _(
                        "Please select the source warehouse location before approving this loading proposal."
                    )
                )
            if effective_source.usage != "internal":
                raise UserError(_("The source location must be an internal location."))
            if effective_source == rec.vehicle_id.stock_location_id:
                raise UserError(
                    _("The source warehouse location and the vehicle location cannot be the same.")
                )
            if rec.source_location_id != effective_source:
                rec.source_location_id = effective_source.id

    def _prepare_picking_vals(self):
        self.ensure_one()
        self._check_ready_for_approval()
        picking_type = self._get_internal_picking_type()
        source_location = self._get_effective_source_location()
        return {
            "picking_type_id": picking_type.id,
            "location_id": source_location.id,
            "location_dest_id": self.vehicle_id.stock_location_id.id,
            "origin": "%s / %s" % (self.plan_id.name or "Route Plan", self.name),
            "company_id": self.env.company.id,
            "move_type": "direct",
            "note": _(
                "Vehicle loading proposal approved for route plan %(plan)s and vehicle %(vehicle)s. Older available lots are allocated first."
            )
            % {
                "plan": self.plan_id.display_name,
                "vehicle": self.vehicle_id.display_name,
            },
        }

    def _prepare_move_vals(self, picking, line):
        self.ensure_one()
        return {
            "product_id": line.product_id.id,
            "product_uom_qty": line.approved_qty,
            "product_uom": line.uom_id.id or line.product_id.uom_id.id,
            "location_id": picking.location_id.id,
            "location_dest_id": picking.location_dest_id.id,
            "picking_id": picking.id,
        }

    def _open_form_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Vehicle Loading Proposal"),
            "res_model": "route.loading.proposal",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_refresh_from_plan(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Only draft loading proposals can be refreshed."))
        return self.action_open_source_location_wizard()

    def action_approve(self):
        self.ensure_one()

        if self.state == "cancelled":
            raise UserError(_("Cancelled loading proposals cannot be approved."))

        approved_lines = self.line_ids.filtered(lambda line: (line.approved_qty or 0.0) > 0)
        if not approved_lines:
            self.write(
                {
                    "state": "approved",
                    "approval_datetime": fields.Datetime.now(),
                }
            )
            return self._open_form_action()

        if self.picking_id and self.picking_id.state != "cancel":
            return self.action_view_transfer()

        picking = self.env["stock.picking"].create(self._prepare_picking_vals())
        for line in approved_lines:
            self.env["stock.move"].create(self._prepare_move_vals(picking, line))

        if picking.state == "draft":
            picking.action_confirm()
        if picking.state in ("confirmed", "waiting"):
            picking.action_assign()

        self._apply_oldest_lot_allocation(picking)

        self.write(
            {
                "picking_id": picking.id,
                "state": "approved",
                "approval_datetime": fields.Datetime.now(),
            }
        )
        return self.action_view_transfer()

    def action_view_transfer(self):
        self.ensure_one()
        if not self.picking_id:
            raise UserError(_("No internal transfer has been created for this proposal yet."))

        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        action["res_id"] = self.picking_id.id
        action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]
        return action

    def action_open_route_plan(self):
        self.ensure_one()
        if not self.plan_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Route Plan"),
            "res_model": "route.plan",
            "res_id": self.plan_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_vehicle_stock_snapshot(self):
        self.ensure_one()
        vehicle = self.vehicle_id
        vehicle_location = getattr(vehicle, "stock_location_id", False)
        if not vehicle or not vehicle_location:
            raise UserError(_("Please set the vehicle stock location first."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Vehicle Stock Snapshot"),
            "res_model": "stock.quant",
            "view_mode": "list,form",
            "views": [
                (self.env.ref("route_core.view_route_vehicle_stock_snapshot_list").id, "list"),
                (False, "form"),
            ],
            "search_view_id": self.env.ref("route_core.view_route_vehicle_stock_snapshot_search").id,
            "target": "current",
            "domain": [
                ("location_id", "child_of", vehicle_location.id),
                ("quantity", ">", 0),
            ],
            "context": {
                "search_default_filter_positive_qty": 1,
                "default_location_id": vehicle_location.id,
            },
        }

    def action_reset_to_draft(self):
        self.ensure_one()
        if self.picking_id and self.picking_id.state not in ("cancel",):
            raise UserError(
                _(
                    "You can only reset the proposal to draft after the linked internal transfer is cancelled."
                )
            )
        self.write(
            {
                "state": "draft",
                "approval_datetime": False,
                "picking_id": False,
            }
        )
        return self._open_form_action()

    def action_cancel(self):
        for rec in self:
            if rec.picking_id and rec.picking_id.state == "done":
                raise UserError(
                    _("You cannot cancel a loading proposal after its internal transfer is done.")
                )
            if rec.picking_id and rec.picking_id.state not in ("cancel", "done"):
                rec.picking_id.action_cancel()
            rec.write({"state": "cancelled"})
        return True


class RouteLoadingProposalLine(models.Model):
    _name = "route.loading.proposal.line"
    _description = "Route Vehicle Loading Proposal Line"
    _order = "suggested_load_qty desc, total_required_qty desc, id"

    proposal_id = fields.Many2one(
        "route.loading.proposal",
        string="Proposal",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="proposal_id.company_id",
        string="Company",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        related="proposal_id.currency_id",
        string="Currency",
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        ondelete="restrict",
        index=True,
    )
    barcode = fields.Char(
        string="Barcode",
        related="product_id.barcode",
        store=False,
        readonly=True,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="UoM",
        related="product_id.uom_id",
        store=False,
        readonly=True,
    )
    planned_outlet_count = fields.Integer(string="Planned Outlets", default=0)
    recent_sales_baseline_qty = fields.Float(string="Recent Sales Baseline", default=0.0)
    outlet_balance_qty = fields.Float(string="Outlet Balance", default=0.0)
    current_outlet_need_qty = fields.Float(string="Current Outlet Need", default=0.0)
    open_shortage_qty = fields.Float(string="Open Shortages", default=0.0)
    movement_profile = fields.Char(string="Movement Speed")
    vehicle_available_qty = fields.Float(string="Vehicle Balance", default=0.0)
    source_available_qty = fields.Float(
        string="Source Balance",
        compute="_compute_source_stock_snapshot",
        store=False,
    )
    earliest_source_expiry_date = fields.Date(
        string="Earliest Source Expiry",
        compute="_compute_source_stock_snapshot",
        store=False,
    )
    source_lot_summary = fields.Char(
        string="Suggested Source Lots",
        compute="_compute_source_stock_snapshot",
        store=False,
    )
    suggested_load_qty = fields.Float(string="Suggested Load Qty", default=0.0)
    approved_qty = fields.Float(string="Approved Qty", default=0.0)
    total_required_qty = fields.Float(
        string="Total Required Qty",
        compute="_compute_totals",
        store=True,
    )
    unit_price = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
        default=0.0,
    )
    required_value = fields.Monetary(
        string="Required Value",
        currency_field="currency_id",
        compute="_compute_values",
        store=True,
    )
    suggested_value = fields.Monetary(
        string="Suggested Value",
        currency_field="currency_id",
        compute="_compute_values",
        store=True,
    )
    approved_value = fields.Monetary(
        string="Approved Value",
        currency_field="currency_id",
        compute="_compute_values",
        store=True,
    )
    outlet_names = fields.Text(string="Affected Outlets")
    basis_note = fields.Text(string="Planning Basis")

    _sql_constraints = [
        (
            "route_loading_proposal_line_product_unique",
            "unique(proposal_id, product_id)",
            "Each product can only appear once in the same loading proposal.",
        ),
    ]

    @api.depends("current_outlet_need_qty", "open_shortage_qty")
    def _compute_totals(self):
        for rec in self:
            rec.total_required_qty = (rec.current_outlet_need_qty or 0.0) + (rec.open_shortage_qty or 0.0)

    @api.depends("total_required_qty", "suggested_load_qty", "approved_qty", "unit_price")
    def _compute_values(self):
        for rec in self:
            price = rec.unit_price or 0.0
            rec.required_value = (rec.total_required_qty or 0.0) * price
            rec.suggested_value = (rec.suggested_load_qty or 0.0) * price
            rec.approved_value = (rec.approved_qty or 0.0) * price

    @api.depends("proposal_id.source_location_id", "product_id")
    def _compute_source_stock_snapshot(self):
        grouped_lines = defaultdict(lambda: self.env["route.loading.proposal.line"])
        for line in self:
            line.source_available_qty = 0.0
            line.earliest_source_expiry_date = False
            line.source_lot_summary = False
            effective_source = line.proposal_id._get_effective_source_location() if line.proposal_id else False
            if effective_source and line.product_id:
                grouped_lines[effective_source.id] |= line

        Quant = self.env["stock.quant"]
        for _location_id, lines in grouped_lines.items():
            location = lines[:1].proposal_id._get_effective_source_location()
            products = lines.mapped("product_id")
            quants = Quant.search(
                [
                    ("location_id", "child_of", location.id),
                    ("product_id", "in", products.ids),
                    ("quantity", ">", 0),
                ]
            )

            qty_map = defaultdict(float)
            lot_names_map = defaultdict(list)
            earliest_expiry_map = {}

            for quant in quants:
                available_qty = lines[:1].proposal_id._get_quant_available_qty(quant)
                if available_qty <= 0 or not quant.product_id:
                    continue
                product_id = quant.product_id.id
                qty_map[product_id] += available_qty
                lot = quant.lot_id
                if not lot:
                    continue
                lot_names_map[product_id].append((lines[:1].proposal_id._lot_sort_key(lot), lot.name or ""))
                lot_date = _lot_priority_date(lot)
                if lot_date and (
                    not earliest_expiry_map.get(product_id)
                    or lot_date < earliest_expiry_map[product_id]
                ):
                    earliest_expiry_map[product_id] = lot_date

            for line in lines:
                product_id = line.product_id.id
                line.source_available_qty = _qty_down(line.product_id, qty_map.get(product_id, 0.0))
                line.earliest_source_expiry_date = earliest_expiry_map.get(product_id)
                lot_names = [name for _key, name in sorted(lot_names_map.get(product_id, [])) if name]
                if lot_names:
                    unique_names = list(dict.fromkeys(lot_names))
                    preview = ", ".join(unique_names[:3])
                    if len(unique_names) > 3:
                        preview = "%s ..." % preview
                    line.source_lot_summary = preview

    @api.onchange("approved_qty")
    def _onchange_approved_qty(self):
        for rec in self:
            rec.approved_qty = _qty_up(rec.product_id, rec.approved_qty)

    @api.model_create_multi
    def create(self, vals_list):
        Product = self.env["product.product"]
        for vals in vals_list:
            product = Product.browse(vals.get("product_id")) if vals.get("product_id") else False
            for field_name in (
                "recent_sales_baseline_qty",
                "current_outlet_need_qty",
                "open_shortage_qty",
                "suggested_load_qty",
                "approved_qty",
            ):
                if field_name in vals:
                    vals[field_name] = _qty_up(product, vals.get(field_name))
            for field_name in ("outlet_balance_qty", "vehicle_available_qty"):
                if field_name in vals:
                    vals[field_name] = _qty_down(product, vals.get(field_name))
        return super().create(vals_list)

    def write(self, vals):
        if any(
            field_name in vals
            for field_name in (
                "recent_sales_baseline_qty",
                "outlet_balance_qty",
                "current_outlet_need_qty",
                "open_shortage_qty",
                "vehicle_available_qty",
                "suggested_load_qty",
                "approved_qty",
            )
        ):
            for rec in self:
                local_vals = dict(vals)
                product = rec.product_id
                for field_name in (
                    "recent_sales_baseline_qty",
                    "current_outlet_need_qty",
                    "open_shortage_qty",
                    "suggested_load_qty",
                    "approved_qty",
                ):
                    if field_name in local_vals:
                        local_vals[field_name] = _qty_up(product, local_vals.get(field_name))
                for field_name in ("outlet_balance_qty", "vehicle_available_qty"):
                    if field_name in local_vals:
                        local_vals[field_name] = _qty_down(product, local_vals.get(field_name))
                super(RouteLoadingProposalLine, rec).write(local_vals)
            return True
        return super().write(vals)

    @api.constrains(
        "recent_sales_baseline_qty",
        "outlet_balance_qty",
        "current_outlet_need_qty",
        "open_shortage_qty",
        "vehicle_available_qty",
        "suggested_load_qty",
        "approved_qty",
        "unit_price",
    )
    def _check_non_negative_values(self):
        for rec in self:
            values = [
                rec.recent_sales_baseline_qty,
                rec.outlet_balance_qty,
                rec.current_outlet_need_qty,
                rec.open_shortage_qty,
                rec.vehicle_available_qty,
                rec.suggested_load_qty,
                rec.approved_qty,
                rec.unit_price,
            ]
            if any((value or 0.0) < 0 for value in values):
                raise ValidationError(_("Loading proposal quantities and prices cannot be negative."))


class RoutePlan(models.Model):
    _inherit = "route.plan"

    loading_proposal_ids = fields.One2many(
        "route.loading.proposal",
        "plan_id",
        string="Loading Proposals",
    )
    loading_proposal_count = fields.Integer(
        string="Loading Proposals",
        compute="_compute_loading_proposal_stats",
        store=False,
    )
    loading_proposal_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("cancelled", "Cancelled"),
        ],
        string="Loading Proposal Status",
        compute="_compute_loading_proposal_stats",
        store=False,
    )

    def _compute_loading_proposal_stats(self):
        Proposal = self.env["route.loading.proposal"].sudo()
        grouped = {}
        if self.ids:
            for proposal in Proposal.search([("plan_id", "in", self.ids)], order="id desc"):
                grouped.setdefault(proposal.plan_id.id, []).append(proposal)
        for rec in self:
            proposals = grouped.get(rec.id, [])
            rec.loading_proposal_count = len(proposals)
            rec.loading_proposal_state = proposals[0].state if proposals else False

    def _get_active_loading_proposal(self):
        self.ensure_one()
        return self.env["route.loading.proposal"].sudo().search(
            [("plan_id", "=", self.id)],
            order="id desc",
            limit=1,
        )

    def _get_loading_vehicle_qty_map(self):
        self.ensure_one()
        vehicle_location = getattr(self.vehicle_id, "stock_location_id", False)
        qty_map = defaultdict(float)
        if not vehicle_location:
            return qty_map

        proposal = self._get_active_loading_proposal()
        helper = proposal or self.env["route.loading.proposal"]
        quants = self.env["stock.quant"].search(
            [
                ("location_id", "child_of", vehicle_location.id),
                ("quantity", ">", 0),
            ]
        )
        for quant in quants:
            if quant.product_id:
                if proposal:
                    qty_map[quant.product_id.id] += proposal._get_quant_available_qty(quant)
                else:
                    reserved = quant.reserved_quantity if "reserved_quantity" in quant._fields else 0.0
                    qty_map[quant.product_id.id] += max((quant.quantity or 0.0) - (reserved or 0.0), 0.0)
        return qty_map

    def _get_product_movement_profiles(self, outlets, reference_date, candidate_products_by_outlet):
        self.ensure_one()
        product_ids = sorted({
            product_id
            for product_set in candidate_products_by_outlet.values()
            for product_id in product_set
        })
        if not product_ids:
            return {}

        lookback_start = reference_date - relativedelta(days=180)
        profile_lines = self.env["route.visit.line"].search(
            [
                ("visit_id.outlet_id", "in", outlets.ids),
                ("product_id", "in", product_ids),
                ("visit_id.state", "!=", "cancel"),
                ("visit_id.date", "<=", reference_date),
                ("visit_id.date", ">=", lookback_start),
            ]
        )
        direct_sale_outlets = outlets.filtered(lambda outlet: (getattr(outlet, "outlet_operation_mode", False) or "") in ("direct_sale", "direct_sales"))
        direct_sale_lines = self.env["sale.order.line"].search(
            [
                ("order_id.route_order_mode", "=", "direct_sale"),
                ("order_id.route_outlet_id", "in", direct_sale_outlets.ids),
                ("order_id.state", "in", ["sale", "done"]),
                ("product_id", "in", product_ids),
                ("display_type", "=", False),
                ("order_id.date_order", ">=", fields.Datetime.to_datetime(str(lookback_start) + " 00:00:00")),
                ("order_id.date_order", "<=", fields.Datetime.to_datetime(str(reference_date) + " 23:59:59")),
            ]
        ) if direct_sale_outlets else self.env["sale.order.line"]

        profile_lines = sorted(
            profile_lines,
            key=lambda line: (
                line.visit_id.date or reference_date,
                line.id,
            ),
            reverse=True,
        )
        direct_sale_lines = sorted(
            direct_sale_lines,
            key=lambda line: (
                line.order_id.date_order or fields.Datetime.to_datetime(str(reference_date) + " 00:00:00"),
                line.id,
            ),
            reverse=True,
        )

        latest_status_by_pair = {}
        counts_by_product = defaultdict(lambda: defaultdict(int))
        for line in profile_lines:
            outlet = line.visit_id.outlet_id
            if not outlet or not line.product_id:
                continue
            key = (outlet.id, line.product_id.id)
            if key in latest_status_by_pair:
                continue
            status = line.movement_status or "no_sale_history"
            latest_status_by_pair[key] = status
            counts_by_product[line.product_id.id][status] += 1
        for line in direct_sale_lines:
            outlet = line.order_id.route_outlet_id
            if not outlet or not line.product_id:
                continue
            key = (outlet.id, line.product_id.id)
            if key in latest_status_by_pair:
                continue
            latest_status_by_pair[key] = "active"
            counts_by_product[line.product_id.id]["active"] += 1

        profile_map = {}
        for product_id in product_ids:
            counts = counts_by_product.get(product_id, {})
            if not counts:
                profile_map[product_id] = "No movement history"
                continue
            if counts.get("active"):
                profile_map[product_id] = "Fast / Active"
            elif counts.get("watch"):
                profile_map[product_id] = "Watch"
            elif counts.get("slow") or counts.get("very_slow"):
                profile_map[product_id] = "Slow"
            elif counts.get("no_sale_history"):
                profile_map[product_id] = "No sale history"
            else:
                profile_map[product_id] = "Mixed"
        return profile_map

    def _build_loading_proposal_line_vals(self):
        self.ensure_one()

        if not self.planning_finalized:
            raise UserError(
                _(
                    "Finalize the vehicle's daily route plan first. The loading proposal must be based on the final daily plan."
                )
            )
        if self.state == "cancel":
            raise UserError(_("You cannot generate a loading proposal for a cancelled route plan."))
        if not self.vehicle_id:
            raise UserError(_("Please select a vehicle before generating a loading proposal."))
        if not getattr(self.vehicle_id, "stock_location_id", False):
            raise UserError(
                _("Vehicle '%s' does not have a vehicle stock location.")
                % (self.vehicle_id.display_name,)
            )

        outlets = self.line_ids.mapped("outlet_id").filtered(lambda outlet: outlet)
        if not outlets:
            raise UserError(_("Please add at least one planned visit before generating a loading proposal."))

        reference_date = self.date or fields.Date.context_today(self)
        lookback_start = reference_date - relativedelta(days=90)

        consignment_outlets = outlets.filtered(
            lambda outlet: (getattr(outlet, "outlet_operation_mode", False) or "") not in ("direct_sale", "direct_sales")
        )
        direct_sale_outlets = outlets.filtered(
            lambda outlet: (getattr(outlet, "outlet_operation_mode", False) or "") in ("direct_sale", "direct_sales")
        )

        recent_lines = self.env["route.visit.line"].search(
            [
                ("visit_id.outlet_id", "in", consignment_outlets.ids),
                ("visit_id.state", "!=", "cancel"),
                ("visit_id.date", "<=", reference_date),
                ("visit_id.date", ">=", lookback_start),
                ("sold_qty", ">", 0),
            ]
        ) if consignment_outlets else self.env["route.visit.line"]

        recent_direct_sale_lines = self.env["sale.order.line"].search(
            [
                ("order_id.route_order_mode", "=", "direct_sale"),
                ("order_id.route_outlet_id", "in", direct_sale_outlets.ids),
                ("order_id.state", "in", ["sale", "done"]),
                ("display_type", "=", False),
                ("product_id", "!=", False),
                ("product_uom_qty", ">", 0),
                ("order_id.date_order", ">=", fields.Datetime.to_datetime(str(lookback_start) + " 00:00:00")),
                ("order_id.date_order", "<=", fields.Datetime.to_datetime(str(reference_date) + " 23:59:59")),
            ]
        ) if direct_sale_outlets else self.env["sale.order.line"]

        shortage_lines = self.env["route.shortage.line"].search(
            [
                ("shortage_id.outlet_id", "in", outlets.ids),
                ("shortage_id.state", "in", ["open", "planned"]),
                ("qty_remaining", ">", 0),
            ]
        )

        candidate_products_by_outlet = defaultdict(set)
        sales_entries = defaultdict(list)
        balance_qty_map = {}
        product_price_map = {}
        shortage_qty_map = defaultdict(float)
        aggregate = {}

        for outlet in consignment_outlets:
            for balance in outlet.stock_balance_ids.filtered("product_id"):
                key = (outlet.id, balance.product_id.id)
                balance_qty_map[key] = _qty_down(balance.product_id, balance.qty or 0.0)
                if balance.unit_price and not product_price_map.get(balance.product_id.id):
                    product_price_map[balance.product_id.id] = balance.unit_price
                candidate_products_by_outlet[outlet.id].add(balance.product_id.id)

        for line in recent_lines:
            outlet = line.visit_id.outlet_id
            product = line.product_id
            if not outlet or not product:
                continue
            key = (outlet.id, product.id)
            sales_entries[key].append((line.visit_id.date or reference_date, line.id, line.sold_qty or 0.0))
            candidate_products_by_outlet[outlet.id].add(product.id)

        for line in recent_direct_sale_lines:
            outlet = line.order_id.route_outlet_id
            product = line.product_id
            if not outlet or not product:
                continue
            line_uom = getattr(line, "product_uom", False) or getattr(line, "product_uom_id", False) or product.uom_id
            sold_qty = line.product_uom_qty or 0.0
            if line_uom and product.uom_id and line_uom != product.uom_id:
                sold_qty = line_uom._compute_quantity(sold_qty, product.uom_id)
            key = (outlet.id, product.id)
            sales_date = fields.Date.to_date(line.order_id.date_order) if line.order_id.date_order else reference_date
            sales_entries[key].append((sales_date or reference_date, line.id, sold_qty))
            candidate_products_by_outlet[outlet.id].add(product.id)
            if getattr(line, "price_unit", False) and not product_price_map.get(product.id):
                product_price_map[product.id] = line.price_unit

        for shortage_line in shortage_lines:
            outlet = shortage_line.shortage_id.outlet_id
            product = shortage_line.product_id
            if not outlet or not product:
                continue
            key = (outlet.id, product.id)
            shortage_qty_map[key] += _qty_up(product, shortage_line.qty_remaining or 0.0)
            candidate_products_by_outlet[outlet.id].add(product.id)
            if shortage_line.unit_price and not product_price_map.get(product.id):
                product_price_map[product.id] = shortage_line.unit_price

        baseline_qty_map = {}
        for key, entries in sales_entries.items():
            recent_entries = sorted(entries, key=lambda item: (item[0], item[1]), reverse=True)[:3]
            if recent_entries:
                baseline_qty_map[key] = _qty_up(self.env["product.product"].browse(key[1]), sum(item[2] for item in recent_entries) / len(recent_entries))

        movement_profile_map = self._get_product_movement_profiles(
            outlets,
            reference_date,
            candidate_products_by_outlet,
        )
        vehicle_qty_map = self._get_loading_vehicle_qty_map()

        for outlet in outlets:
            product_ids = candidate_products_by_outlet.get(outlet.id, set())
            is_direct_sale_outlet = (getattr(outlet, "outlet_operation_mode", False) or "") in ("direct_sale", "direct_sales")
            for product_id in product_ids:
                stock_qty = 0.0 if is_direct_sale_outlet else balance_qty_map.get((outlet.id, product_id), 0.0)
                baseline_qty = baseline_qty_map.get((outlet.id, product_id), 0.0)
                shortage_qty = shortage_qty_map.get((outlet.id, product_id), 0.0)
                if is_direct_sale_outlet:
                    current_need_qty = _qty_up(self.env["product.product"].browse(product_id), baseline_qty or 0.0)
                else:
                    current_need_qty = _qty_up(self.env["product.product"].browse(product_id), max((baseline_qty or 0.0) - (stock_qty or 0.0), 0.0))

                if current_need_qty <= 0 and shortage_qty <= 0:
                    continue

                bucket = aggregate.setdefault(
                    product_id,
                    {
                        "planned_outlet_count": 0,
                        "recent_sales_baseline_qty": 0.0,
                        "outlet_balance_qty": 0.0,
                        "current_outlet_need_qty": 0.0,
                        "open_shortage_qty": 0.0,
                        "outlet_names": set(),
                    },
                )
                bucket["planned_outlet_count"] += 1
                bucket["recent_sales_baseline_qty"] += baseline_qty
                bucket["outlet_balance_qty"] += stock_qty
                bucket["current_outlet_need_qty"] += current_need_qty
                bucket["open_shortage_qty"] += shortage_qty
                bucket["outlet_names"].add(outlet.display_name or outlet.name)

        if not aggregate:
            return []

        products = self.env["product.product"].browse(list(aggregate.keys())).exists()
        product_map = {product.id: product for product in products}
        line_vals = []

        for product_id, bucket in aggregate.items():
            product = product_map.get(product_id)
            if not product:
                continue

            total_required_qty = (bucket["current_outlet_need_qty"] or 0.0) + (bucket["open_shortage_qty"] or 0.0)
            vehicle_available_qty = _qty_down(product, vehicle_qty_map.get(product_id, 0.0))
            total_required_qty = _qty_up(product, total_required_qty)
            suggested_load_qty = _qty_up(product, max(total_required_qty - vehicle_available_qty, 0.0))
            outlet_names = sorted(bucket["outlet_names"])
            unit_price = product_price_map.get(product_id) or product.lst_price or 0.0

            basis_parts = [
                _(
                    "Recent demand baseline (last 90 days, up to 3 recent consignment sold visits or direct-sale orders): %(qty).2f"
                )
                % {"qty": bucket["recent_sales_baseline_qty"]},
                _("Outlet balance: %(qty).2f") % {"qty": bucket["outlet_balance_qty"]},
                _("Current outlet need: %(qty).2f") % {"qty": bucket["current_outlet_need_qty"]},
                _("Open shortages: %(qty).2f") % {"qty": bucket["open_shortage_qty"]},
                _("Vehicle balance: %(qty).2f") % {"qty": vehicle_available_qty},
                _("Movement speed: %(label)s") % {"label": movement_profile_map.get(product_id) or _("No movement history")},
            ]

            line_vals.append(
                {
                    "product_id": product_id,
                    "planned_outlet_count": bucket["planned_outlet_count"],
                    "recent_sales_baseline_qty": bucket["recent_sales_baseline_qty"],
                    "outlet_balance_qty": bucket["outlet_balance_qty"],
                    "current_outlet_need_qty": bucket["current_outlet_need_qty"],
                    "open_shortage_qty": bucket["open_shortage_qty"],
                    "movement_profile": movement_profile_map.get(product_id) or _("No movement history"),
                    "vehicle_available_qty": vehicle_available_qty,
                    "suggested_load_qty": suggested_load_qty,
                    "approved_qty": suggested_load_qty,
                    "unit_price": unit_price,
                    "outlet_names": "\n".join(outlet_names),
                    "basis_note": " | ".join(basis_parts),
                }
            )

        line_vals.sort(
            key=lambda vals: (
                -(vals.get("suggested_load_qty") or 0.0),
                -(vals.get("current_outlet_need_qty", 0.0) + vals.get("open_shortage_qty", 0.0)),
                self.env["product.product"].browse(vals["product_id"]).display_name or "",
            )
        )
        return line_vals

    def _get_loading_source_wizard_action(self, proposal=False):
        self.ensure_one()
        helper_proposal = proposal or self.env["route.loading.proposal"].new(
            {
                "plan_id": self.id,
                "company_id": self.env.company.id,
            }
        )
        default_source = proposal.source_location_id if proposal else False
        default_source = default_source or helper_proposal._get_default_source_location()
        return {
            "type": "ir.actions.act_window",
            "name": _("Choose Loading Source"),
            "res_model": "route.loading.source.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_plan_id": self.id,
                "default_proposal_id": proposal.id if proposal else False,
                "default_source_location_id": default_source.id if default_source else False,
            },
        }

    def action_generate_loading_proposal(self):
        self.ensure_one()

        if not self.planning_finalized:
            raise UserError(
                _(
                    "Finalize the vehicle's daily route plan first, then generate the loading proposal from that final plan."
                )
            )

        proposal = self._get_active_loading_proposal()
        if proposal and proposal.state == "approved" and proposal.picking_id and proposal.picking_id.state != "cancel":
            return proposal._open_form_action()

        return self._get_loading_source_wizard_action(proposal=proposal)

    def _generate_loading_proposal_with_source(self, source_location, proposal=False):
        self.ensure_one()

        if not self.planning_finalized:
            raise UserError(
                _(
                    "Finalize the vehicle's daily route plan first, then generate the loading proposal from that final plan."
                )
            )
        if not source_location:
            raise UserError(_("Please choose a source warehouse location first."))
        if source_location.usage != "internal":
            raise UserError(_("The source location must be an internal location."))
        if self.vehicle_id and getattr(self.vehicle_id, "stock_location_id", False) and source_location == self.vehicle_id.stock_location_id:
            raise UserError(_("The source warehouse location and the vehicle location cannot be the same."))

        proposal = proposal or self._get_active_loading_proposal()
        if proposal and proposal.state == "approved" and proposal.picking_id and proposal.picking_id.state != "cancel":
            return proposal

        line_vals = self._build_loading_proposal_line_vals()

        note = _(
            "Generated from the finalized daily route plan using planned visits, open shortages, current outlet stock balances, recent consignment sales history, recent direct-sale order history, product movement speed, and current vehicle balance. "
            "Suggested load qty = max((current outlet need + open shortages) - vehicle balance, 0). Direct-sale outlets use recent direct-sale demand as the need baseline, while consignment outlets use outlet balance versus recent sold visits. "
            "Supervisor-selected source location: %(source)s. "
            "When the transfer is created, older available lots are allocated first."
        ) % {"source": source_location.display_name}

        if proposal:
            reset_vals = {
                "state": "draft",
                "approval_datetime": False,
                "note": note,
                "source_location_id": source_location.id,
            }
            if proposal.picking_id and proposal.picking_id.state == "cancel":
                reset_vals["picking_id"] = False
            proposal.write(reset_vals)
            proposal.line_ids.unlink()
        else:
            create_vals = {
                "plan_id": self.id,
                "company_id": self.env.company.id,
                "note": note,
                "source_location_id": source_location.id,
            }
            proposal = self.env["route.loading.proposal"].create(create_vals)

        if line_vals:
            self.env["route.loading.proposal.line"].create(
                [dict(vals, proposal_id=proposal.id) for vals in line_vals]
            )

        return proposal

    def action_view_loading_proposal(self):
        self.ensure_one()
        proposal = self._get_active_loading_proposal()
        if not proposal:
            raise UserError(_("No loading proposal has been generated for this route plan yet."))
        return proposal._open_form_action()

    def action_open_vehicle_stock_snapshot(self):
        self.ensure_one()
        vehicle = self.vehicle_id
        vehicle_location = getattr(vehicle, "stock_location_id", False)
        if not vehicle or not vehicle_location:
            raise UserError(_("Please set the vehicle stock location first."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Vehicle Stock Snapshot"),
            "res_model": "stock.quant",
            "view_mode": "list,form",
            "views": [
                (self.env.ref("route_core.view_route_vehicle_stock_snapshot_list").id, "list"),
                (False, "form"),
            ],
            "search_view_id": self.env.ref("route_core.view_route_vehicle_stock_snapshot_search").id,
            "target": "current",
            "domain": [
                ("location_id", "child_of", vehicle_location.id),
                ("quantity", ">", 0),
            ],
            "context": {
                "search_default_filter_positive_qty": 1,
                "default_location_id": vehicle_location.id,
            },
        }




