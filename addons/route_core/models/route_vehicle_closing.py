from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RouteVehicleClosing(models.Model):
    _name = "route.vehicle.closing"
    _description = "Route Vehicle End of Day Closing"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "plan_date desc, id desc"

    name = fields.Char(string="Closing Reference", required=True, copy=False, readonly=True, default="New", tracking=True)
    plan_id = fields.Many2one("route.plan", string="Route Plan", required=True, ondelete="cascade", tracking=True)
    company_id = fields.Many2one("res.company", string="Company", required=True, readonly=True, default=lambda self: self.env.company)
    plan_date = fields.Date(string="Plan Date", related="plan_id.date", store=True, readonly=True)
    vehicle_id = fields.Many2one("route.vehicle", string="Vehicle", related="plan_id.vehicle_id", store=True, readonly=True)
    user_id = fields.Many2one("res.users", string="Salesperson", related="plan_id.user_id", store=True, readonly=True)
    planning_finalized = fields.Boolean(string="Daily Planning Finalized", related="plan_id.planning_finalized", readonly=True, store=False)
    planning_finalized_datetime = fields.Datetime(string="Planning Finalized On", related="plan_id.planning_finalized_datetime", readonly=True, store=False)
    vehicle_location_id = fields.Many2one("stock.location", string="Vehicle Location", related="vehicle_id.stock_location_id", readonly=True, store=False)
    state = fields.Selection([
        ("draft", "Draft"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    ], string="Status", default="draft", required=True, tracking=True)
    snapshot_datetime = fields.Datetime(string="Snapshot Refreshed On", readonly=True, copy=False)
    close_datetime = fields.Datetime(string="Closed On", readonly=True, copy=False, tracking=True)
    count_started_datetime = fields.Datetime(string="Count Started On", readonly=True, copy=False, tracking=True)
    count_done = fields.Boolean(string="Count Completed", readonly=True, copy=False, tracking=True)
    count_done_datetime = fields.Datetime(string="Count Completed On", readonly=True, copy=False, tracking=True)
    variance_review_started_datetime = fields.Datetime(string="Variance Review Started On", readonly=True, copy=False, tracking=True)
    variance_review_done = fields.Boolean(string="Variance Review Completed", readonly=True, copy=False, tracking=True)
    variance_review_done_datetime = fields.Datetime(string="Variance Review Completed On", readonly=True, copy=False, tracking=True)
    note = fields.Text(string="Notes")
    line_ids = fields.One2many("route.vehicle.closing.line", "closing_id", string="Closing Lines", copy=True)
    reconciliation_picking_ids = fields.One2many("stock.picking", "vehicle_closing_id", string="Reconciliation Transfers", readonly=True)

    line_count = fields.Integer(string="Line Count", compute="_compute_totals")
    variance_line_count = fields.Integer(string="Variance Lines", compute="_compute_totals")
    reviewed_variance_line_count = fields.Integer(string="Reviewed Variance Lines", compute="_compute_totals")
    pending_variance_line_count = fields.Integer(string="Pending Variance Lines", compute="_compute_totals")
    executable_variance_line_count = fields.Integer(string="Executable Variance Lines", compute="_compute_totals")
    pending_execution_line_count = fields.Integer(string="Pending Execution Lines", compute="_compute_totals")
    executed_variance_line_count = fields.Integer(string="Executed Variance Lines", compute="_compute_totals")
    reconciliation_picking_count = fields.Integer(string="Reconciliation Transfers", compute="_compute_totals")
    total_system_qty = fields.Float(string="System Qty", compute="_compute_totals")
    total_counted_qty = fields.Float(string="Counted Qty", compute="_compute_totals")
    total_variance_qty = fields.Float(string="Net Variance Qty", compute="_compute_totals")
    total_abs_variance_qty = fields.Float(string="Absolute Variance Qty", compute="_compute_totals")
    variance_review_status = fields.Selection([
        ("clean", "No Variances"),
        ("pending", "Pending Review"),
        ("in_progress", "Review In Progress"),
        ("done", "Review Completed"),
    ], string="Variance Review Status", compute="_compute_totals")
    reconciliation_execution_status = fields.Selection([
        ("not_needed", "No Execution Needed"),
        ("pending", "Execution Pending"),
        ("done", "Execution Completed"),
    ], string="Reconciliation Execution Status", compute="_compute_totals")

    _sql_constraints = [(
        "route_vehicle_closing_plan_unique",
        "unique(plan_id)",
        "Only one vehicle closing is allowed for each route plan.",
    )]

    @api.depends(
        "line_ids",
        "line_ids.system_qty",
        "line_ids.counted_qty",
        "line_ids.variance_qty",
        "line_ids.review_status",
        "line_ids.action_execution_status",
        "line_ids.reconciliation_action",
        "variance_review_started_datetime",
        "variance_review_done",
        "reconciliation_picking_ids",
    )
    def _compute_totals(self):
        for rec in self:
            variance_lines = rec.line_ids.filtered(lambda line: abs(line.variance_qty or 0.0) > 0.0001)
            reviewed_variance_lines = variance_lines.filtered(lambda line: line.review_status == "reviewed")
            executable_lines = rec._get_executable_variance_lines()
            executed_lines = executable_lines.filtered(lambda line: line.action_execution_status == "done")
            rec.line_count = len(rec.line_ids)
            rec.variance_line_count = len(variance_lines)
            rec.reviewed_variance_line_count = len(reviewed_variance_lines)
            rec.pending_variance_line_count = len(variance_lines) - len(reviewed_variance_lines)
            rec.executable_variance_line_count = len(executable_lines)
            rec.executed_variance_line_count = len(executed_lines)
            rec.pending_execution_line_count = len(executable_lines) - len(executed_lines)
            rec.reconciliation_picking_count = len(rec.reconciliation_picking_ids)
            rec.total_system_qty = sum(rec.line_ids.mapped("system_qty"))
            rec.total_counted_qty = sum(rec.line_ids.mapped("counted_qty"))
            rec.total_variance_qty = sum(rec.line_ids.mapped("variance_qty"))
            rec.total_abs_variance_qty = sum(abs(line.variance_qty or 0.0) for line in rec.line_ids)
            if not variance_lines:
                rec.variance_review_status = "clean"
            elif rec.variance_review_done:
                rec.variance_review_status = "done"
            elif rec.variance_review_started_datetime:
                rec.variance_review_status = "in_progress"
            else:
                rec.variance_review_status = "pending"

            if not executable_lines:
                rec.reconciliation_execution_status = "not_needed"
            elif len(executed_lines) == len(executable_lines):
                rec.reconciliation_execution_status = "done"
            else:
                rec.reconciliation_execution_status = "pending"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("route.vehicle.closing") or "New"
        return super().create(vals_list)

    def _open_form_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Vehicle Closing"),
            "res_model": "route.vehicle.closing",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def _open_scan_wizard_action(self):
        self.ensure_one()
        wizard = self.env["route.vehicle.closing.scan.wizard"].create({"closing_id": self.id})
        return {
            "type": "ir.actions.act_window",
            "name": _("Scan Vehicle Stock"),
            "res_model": "route.vehicle.closing.scan.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def _get_vehicle_quants(self):
        self.ensure_one()
        vehicle_location = self.vehicle_location_id
        if not vehicle_location:
            raise UserError(_("Please set the vehicle stock location first."))
        return self.env["stock.quant"].search([
            ("location_id", "child_of", vehicle_location.id),
            ("quantity", "!=", 0),
        ], order="product_id, lot_id, location_id, id")

    def _build_snapshot_line_vals(self):
        self.ensure_one()
        existing_map = {}
        for line in self.line_ids:
            key = (line.product_id.id, line.lot_id.id or False, line.location_id.id)
            existing_map[key] = {
                "counted_qty": line.counted_qty,
                "note": line.note,
                "variance_reason": line.variance_reason,
                "reconciliation_action": line.reconciliation_action,
                "review_note": line.review_note,
                "generated_picking_id": line.generated_picking_id.id,
            }

        line_vals = []
        for quant in self._get_vehicle_quants():
            if not quant.product_id:
                continue
            reserved_qty = getattr(quant, "reserved_quantity", 0.0) or 0.0
            system_qty = quant.quantity or 0.0
            available_qty = max(system_qty - reserved_qty, 0.0)
            key = (quant.product_id.id, quant.lot_id.id or False, quant.location_id.id)
            previous = existing_map.get(key, {})
            line_vals.append({
                "product_id": quant.product_id.id,
                "location_id": quant.location_id.id,
                "lot_id": quant.lot_id.id or False,
                "in_date": quant.in_date,
                "system_qty": system_qty,
                "reserved_qty": reserved_qty,
                "available_qty": available_qty,
                "counted_qty": previous.get("counted_qty", system_qty),
                "note": previous.get("note", False),
                "variance_reason": previous.get("variance_reason", False),
                "reconciliation_action": previous.get("reconciliation_action", False),
                "review_note": previous.get("review_note", False),
                "generated_picking_id": previous.get("generated_picking_id", False),
            })

        line_vals.sort(key=lambda vals: (
            self.env["product.product"].browse(vals["product_id"]).display_name or "",
            vals.get("location_id") or 0,
            vals.get("lot_id") or 0,
        ))
        return line_vals

    def action_refresh_snapshot(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("You can refresh the vehicle closing snapshot only while it is in draft."))
            line_vals = rec._build_snapshot_line_vals()
            rec.line_ids.unlink()
            if line_vals:
                self.env["route.vehicle.closing.line"].create([dict(vals, closing_id=rec.id) for vals in line_vals])
            rec.snapshot_datetime = fields.Datetime.now()
            if not rec.count_started_datetime:
                rec.line_ids.write({"counted_qty": 0.0})
                for line in rec.line_ids:
                    line.counted_qty = line.system_qty
        return True

    def action_start_count(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("You can start the vehicle count only while the closing is in draft."))
        if not self.line_ids:
            self.action_refresh_snapshot()
        self.line_ids.write({"counted_qty": 0.0})
        self.count_started_datetime = fields.Datetime.now()
        self.count_done = False
        self.count_done_datetime = False
        self.message_post(body=_("Vehicle physical count started. Scan products or lots to build the counted quantities."))
        return self._open_scan_wizard_action()

    def action_open_scan_wizard(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("You can scan vehicle stock only while the closing is in draft."))
        if not self.count_started_datetime:
            raise UserError(_("Please start the count first."))
        self.count_done = False
        self.count_done_datetime = False
        return self._open_scan_wizard_action()

    def action_mark_count_done(self):
        for rec in self:
            if rec.state != "draft":
                continue
            if not rec.count_started_datetime:
                raise UserError(_("Please start the count first."))
            rec.count_done = True
            rec.count_done_datetime = fields.Datetime.now()
            rec.message_post(body=_("Vehicle count marked as completed."))
        return True

    def action_close_day(self):
        for rec in self:
            if rec.state != "draft":
                continue
            if not rec.count_started_datetime:
                raise UserError(_("Please start the vehicle count before closing the day."))
            if not rec.count_done:
                raise UserError(_("Please finish the vehicle count first, then close the day."))
            if not rec.vehicle_id:
                raise UserError(_("The closing record is missing a vehicle."))
            if not rec.vehicle_location_id:
                raise UserError(_("Please set the vehicle stock location first."))
            if not rec.line_ids:
                rec.action_refresh_snapshot()
            close_time = fields.Datetime.now()
            vals = {"state": "closed", "close_datetime": close_time}
            if not rec.variance_line_count:
                vals.update({
                    "variance_review_done": True,
                    "variance_review_done_datetime": close_time,
                })
            rec.write(vals)
            if rec.variance_line_count:
                rec.message_post(body=_("Vehicle day closed with %(count)s variance line(s). Net variance qty: %(qty).2f. Start variance review to classify the differences.") % {"count": rec.variance_line_count, "qty": rec.total_variance_qty})
            else:
                rec.message_post(body=_("Vehicle day closed with no stock variance."))
        return True

    def action_start_variance_review(self):
        for rec in self:
            if rec.state != "closed":
                raise UserError(_("Variance review can start only after the vehicle day is closed."))
            if not rec.variance_line_count:
                raise UserError(_("There are no variance lines to review."))
            rec.variance_review_started_datetime = fields.Datetime.now()
            rec.variance_review_done = False
            rec.variance_review_done_datetime = False
            rec.message_post(body=_("Variance review started. Please classify each variance line and choose a reconciliation action."))
        return True

    def action_complete_variance_review(self):
        for rec in self:
            if rec.state != "closed":
                raise UserError(_("Variance review can be completed only after the vehicle day is closed."))
            if not rec.variance_line_count:
                raise UserError(_("There are no variance lines to review."))
            pending_lines = rec.line_ids.filtered(lambda line: line.review_status == "pending")
            if pending_lines:
                raise UserError(_("Please review all variance lines before completing the variance review."))
            rec.variance_review_done = True
            rec.variance_review_done_datetime = fields.Datetime.now()
            rec.message_post(body=_("Variance review completed. All variance lines now have a reason and reconciliation action."))
        return True

    def _get_location_ancestors(self, location):
        ancestors = self.env["stock.location"]
        current = location
        while current:
            ancestors |= current
            current = current.location_id
        return ancestors

    def _get_main_warehouse(self):
        self.ensure_one()
        if not self.vehicle_location_id:
            return False

        warehouse_model = self.env["stock.warehouse"]
        ancestors = []
        current = self.vehicle_location_id
        while current:
            ancestors.append(current)
            current = current.location_id
        ancestor_ids = [loc.id for loc in ancestors]

        for location in reversed(ancestors):
            warehouse = warehouse_model.search([
                ("lot_stock_id", "=", location.id),
                "|",
                ("company_id", "=", self.company_id.id),
                ("company_id", "=", False),
            ], order="company_id desc, id asc", limit=1)
            if warehouse:
                return warehouse

        for location in reversed(ancestors):
            warehouse = warehouse_model.search([
                ("view_location_id", "=", location.id),
                "|",
                ("company_id", "=", self.company_id.id),
                ("company_id", "=", False),
            ], order="company_id desc, id asc", limit=1)
            if warehouse:
                return warehouse

        candidate_warehouses = warehouse_model.search([
            "|",
            ("company_id", "=", self.company_id.id),
            ("company_id", "=", False),
        ])
        for warehouse in candidate_warehouses:
            lot_stock = warehouse.lot_stock_id
            view_location = warehouse.view_location_id
            if lot_stock and lot_stock.id in ancestor_ids:
                return warehouse
            if view_location and view_location.id in ancestor_ids:
                return warehouse
        return False

    def _get_main_warehouse_location(self):
        self.ensure_one()
        warehouse = self._get_main_warehouse()
        if warehouse and warehouse.lot_stock_id:
            return warehouse.lot_stock_id
        if not self.vehicle_location_id:
            return False
        root = self._get_root_internal_location(self.vehicle_location_id)
        return root if root and root.usage == "internal" else False

    def _get_internal_picking_type(self):
        self.ensure_one()
        picking_type_model = self.env["stock.picking.type"]
        warehouse = self._get_main_warehouse()
        main_location = self._get_main_warehouse_location()

        if warehouse:
            if "int_type_id" in warehouse._fields and warehouse.int_type_id and warehouse.int_type_id.code == "internal":
                return warehouse.int_type_id

            picking_type = picking_type_model.search([
                ("code", "=", "internal"),
                ("warehouse_id", "=", warehouse.id),
                "|",
                ("company_id", "=", self.company_id.id),
                ("company_id", "=", False),
            ], order="company_id desc, sequence asc, id asc", limit=1)
            if picking_type:
                return picking_type

        if main_location:
            picking_type = picking_type_model.search([
                ("code", "=", "internal"),
                "|",
                ("default_location_src_id", "child_of", main_location.id),
                ("default_location_dest_id", "child_of", main_location.id),
                "|",
                ("company_id", "=", self.company_id.id),
                ("company_id", "=", False),
            ], order="company_id desc, sequence asc, id asc", limit=1)
            if picking_type:
                return picking_type

        picking_type = picking_type_model.search([
            ("code", "=", "internal"),
            "|",
            ("company_id", "=", self.company_id.id),
            ("company_id", "=", False),
        ], order="company_id desc, sequence asc, id asc", limit=1)
        if not picking_type:
            raise UserError(_("No Internal Transfer operation type was found for company '%s'.") % (self.company_id.display_name,))
        return picking_type

    def _get_root_internal_location(self, location):
        root = location
        while root.parent_path and root.location_id and root.location_id.usage == "internal":
            root = root.location_id
        return root

    def _get_return_to_warehouse_location(self):
        self.ensure_one()
        warehouse = self._get_main_warehouse()
        if warehouse and warehouse.lot_stock_id:
            return warehouse.lot_stock_id
        if not self.vehicle_location_id:
            return False
        root = self._get_root_internal_location(self.vehicle_location_id)
        return root if root and root.id != self.vehicle_location_id.id else False

    def _get_reconciliation_destination_location(self, action_code):
        self.ensure_one()
        if action_code == "send_damaged":
            location = self.company_id.return_damaged_location_id
            if not location:
                raise UserError(_("Please configure Return Damaged Location before creating damaged reconciliation transfers."))
            return location
        if action_code == "send_near_expiry":
            location = self.company_id.return_near_expiry_location_id
            if not location:
                raise UserError(_("Please configure Return Near Expiry Location before creating near expiry reconciliation transfers."))
            return location
        if action_code == "return_to_warehouse":
            location = self._get_return_to_warehouse_location()
            if not location:
                raise UserError(_("Could not determine the warehouse return location from the vehicle stock location."))
            return location
        return False

    def _get_executable_variance_lines(self):
        self.ensure_one()
        return self.line_ids.filtered(
            lambda line: abs(line.variance_qty or 0.0) > 0.0001
            and line.variance_qty < 0
            and line.reconciliation_action in ("send_damaged", "send_near_expiry", "return_to_warehouse")
        )

    def action_create_reconciliation_transfers(self):
        for rec in self:
            if rec.state != "closed":
                raise UserError(_("Reconciliation transfers can be created only after closing the vehicle day."))
            if rec.variance_line_count == 0:
                raise UserError(_("There are no variance lines to execute."))
            if not rec.variance_review_done:
                raise UserError(_("Please complete the variance review first."))
            executable_lines = rec._get_executable_variance_lines().filtered(lambda line: not line.generated_picking_id)
            if not executable_lines:
                raise UserError(_("There are no pending executable variance lines."))
            if not rec.vehicle_location_id:
                raise UserError(_("Please configure the vehicle stock location first."))

            grouped_lines = {}
            for line in executable_lines:
                destination = rec._get_reconciliation_destination_location(line.reconciliation_action)
                key = (line.reconciliation_action, destination.id)
                grouped_lines.setdefault(key, {"destination": destination, "lines": self.env["route.vehicle.closing.line"]})
                grouped_lines[key]["lines"] |= line

            created_pickings = self.env["stock.picking"]
            picking_type = rec._get_internal_picking_type()
            move_model = self.env["stock.move"]
            move_line_model = self.env["stock.move.line"]
            move_has_restrict_lot = "restrict_lot_id" in move_model._fields
            move_has_description_picking = "description_picking" in move_model._fields

            action_labels = {
                "send_damaged": _("To Damaged"),
                "send_near_expiry": _("To Near Expiry"),
                "return_to_warehouse": _("Return to Warehouse"),
            }

            for (action_code, _dest_id), payload in grouped_lines.items():
                destination = payload["destination"]
                lines = payload["lines"]
                picking = self.env["stock.picking"].create({
                    "picking_type_id": picking_type.id,
                    "location_id": rec.vehicle_location_id.id,
                    "location_dest_id": destination.id,
                    "origin": "%s - %s" % (rec.name, action_labels.get(action_code, action_code)),
                    "partner_id": rec.plan_id.user_id.partner_id.id if rec.plan_id.user_id and rec.plan_id.user_id.partner_id else False,
                    "move_type": "direct",
                    "company_id": rec.company_id.id,
                    "vehicle_closing_id": rec.id,
                })

                for line in lines:
                    qty = abs(line.variance_qty or 0.0)
                    if qty <= 0:
                        continue
                    move_vals = {
                        "product_id": line.product_id.id,
                        "product_uom_qty": qty,
                        "product_uom": line.uom_id.id or line.product_id.uom_id.id,
                        "location_id": picking.location_id.id,
                        "location_dest_id": picking.location_dest_id.id,
                        "picking_id": picking.id,
                        "company_id": rec.company_id.id,
                        "origin": picking.origin,
                    }
                    if move_has_description_picking:
                        move_vals["description_picking"] = line.product_id.display_name
                    if move_has_restrict_lot and line.lot_id:
                        move_vals["restrict_lot_id"] = line.lot_id.id
                    move = move_model.create(move_vals)
                    if move.state == "draft":
                        move._action_confirm()
                    ml_vals = {
                        "move_id": move.id,
                        "picking_id": picking.id,
                        "product_id": line.product_id.id,
                        "product_uom_id": line.uom_id.id or line.product_id.uom_id.id,
                        "qty_done": qty,
                        "location_id": picking.location_id.id,
                        "location_dest_id": picking.location_dest_id.id,
                    }
                    if line.lot_id:
                        ml_vals["lot_id"] = line.lot_id.id
                    move_line_model.create(ml_vals)
                    line.generated_picking_id = picking.id

                if picking.state == "draft":
                    picking.action_confirm()
                created_pickings |= picking

            rec.message_post(body=_("Created %(count)s reconciliation transfer(s) for executable variance lines.") % {"count": len(created_pickings)})

            if len(created_pickings) == 1:
                return rec.action_view_reconciliation_transfers()
        return True

    def action_view_reconciliation_transfers(self):
        self.ensure_one()
        if not self.reconciliation_picking_ids:
            raise UserError(_("No reconciliation transfers have been created yet."))
        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        if len(self.reconciliation_picking_ids) == 1:
            action["res_id"] = self.reconciliation_picking_ids.id
            action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]
        else:
            action["domain"] = [("id", "in", self.reconciliation_picking_ids.ids)]
        return action

    def action_reset_to_draft(self):
        self.write({
            "state": "draft",
            "close_datetime": False,
            "count_done": False,
            "count_done_datetime": False,
            "variance_review_started_datetime": False,
            "variance_review_done": False,
            "variance_review_done_datetime": False,
        })
        return True

    def action_cancel(self):
        self.write({"state": "cancelled"})
        return True

    def action_open_route_plan(self):
        self.ensure_one()
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
        location = self.vehicle_location_id
        action = self.env.ref("stock.quants_action").sudo().read()[0]
        action["name"] = _("Vehicle Stock Snapshot")
        action["domain"] = [("location_id", "child_of", location.id)] if location else []
        action["context"] = {"search_default_internal_loc": 1}
        return action


class RouteVehicleClosingLine(models.Model):
    _name = "route.vehicle.closing.line"
    _description = "Route Vehicle Closing Line"
    _order = "product_id, location_id, lot_id, id"

    closing_id = fields.Many2one("route.vehicle.closing", string="Vehicle Closing", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", string="Company", related="closing_id.company_id", store=True, readonly=True)
    product_id = fields.Many2one("product.product", string="Product", required=True, readonly=True)
    product_tmpl_id = fields.Many2one("product.template", string="Product Template", related="product_id.product_tmpl_id", store=True, readonly=True)
    barcode = fields.Char(string="Barcode", related="product_id.barcode", store=False, readonly=True)
    uom_id = fields.Many2one("uom.uom", string="UoM", related="product_id.uom_id", store=True, readonly=True)
    location_id = fields.Many2one("stock.location", string="Location", required=True, readonly=True)
    lot_id = fields.Many2one("stock.lot", string="Lot/Serial Number", readonly=True)
    expiry_date = fields.Datetime(string="Expiry Date", related="lot_id.expiration_date", store=False, readonly=True)
    alert_date = fields.Datetime(string="Alert Date", related="lot_id.alert_date", store=False, readonly=True)
    in_date = fields.Datetime(string="Incoming Date", readonly=True)
    system_qty = fields.Float(string="System Qty", digits="Product Unit of Measure", readonly=True)
    reserved_qty = fields.Float(string="Reserved Qty", digits="Product Unit of Measure", readonly=True)
    available_qty = fields.Float(string="Available Qty", digits="Product Unit of Measure", readonly=True)
    counted_qty = fields.Float(string="Counted Qty", digits="Product Unit of Measure")
    variance_qty = fields.Float(string="Variance Qty", digits="Product Unit of Measure", compute="_compute_variance", store=True)
    variance_status = fields.Selection([("match", "Match"), ("short", "Short"), ("over", "Over")], string="Variance Status", compute="_compute_variance", store=True)
    variance_reason = fields.Selection([
        ("missing", "Missing / Lost"),
        ("unrecorded_sale", "Unrecorded Sale"),
        ("damaged", "Damaged / Broken"),
        ("counting_error", "Counting Error"),
        ("extra_load", "Extra Load / Transfer"),
        ("unrecorded_return", "Unrecorded Return"),
        ("previous_error", "Previous Error"),
        ("other", "Other"),
    ], string="Variance Reason")
    reconciliation_action = fields.Selection([
        ("investigate", "Investigate Later"),
        ("stock_adjustment", "Stock Adjustment"),
        ("send_damaged", "Send to Damaged"),
        ("send_near_expiry", "Send to Near Expiry"),
        ("return_to_warehouse", "Return to Warehouse"),
        ("counting_error", "Count Error / Ignore"),
    ], string="Reconciliation Action")
    review_note = fields.Char(string="Review Note")
    review_status = fields.Selection([
        ("clean", "No Variance"),
        ("pending", "Pending Review"),
        ("reviewed", "Reviewed"),
    ], string="Review Status", compute="_compute_review_status")
    generated_picking_id = fields.Many2one("stock.picking", string="Reconciliation Transfer", readonly=True, copy=False)
    action_execution_status = fields.Selection([
        ("not_needed", "No Execution Needed"),
        ("pending", "Pending Execution"),
        ("done", "Transfer Created"),
    ], string="Execution Status", compute="_compute_action_execution_status")
    note = fields.Char(string="Line Note")

    @api.depends("system_qty", "counted_qty")
    def _compute_variance(self):
        for rec in self:
            rec.variance_qty = (rec.counted_qty or 0.0) - (rec.system_qty or 0.0)
            if abs(rec.variance_qty) <= 0.0001:
                rec.variance_status = "match"
            elif rec.variance_qty < 0:
                rec.variance_status = "short"
            else:
                rec.variance_status = "over"

    @api.depends("variance_qty", "variance_reason", "reconciliation_action")
    def _compute_review_status(self):
        for rec in self:
            if abs(rec.variance_qty or 0.0) <= 0.0001:
                rec.review_status = "clean"
            elif rec.variance_reason and rec.reconciliation_action:
                rec.review_status = "reviewed"
            else:
                rec.review_status = "pending"

    @api.depends("variance_qty", "reconciliation_action", "generated_picking_id")
    def _compute_action_execution_status(self):
        executable_actions = {"send_damaged", "send_near_expiry", "return_to_warehouse"}
        for rec in self:
            if abs(rec.variance_qty or 0.0) <= 0.0001 or rec.variance_qty >= 0 or rec.reconciliation_action not in executable_actions:
                rec.action_execution_status = "not_needed"
            elif rec.generated_picking_id:
                rec.action_execution_status = "done"
            else:
                rec.action_execution_status = "pending"


class RoutePlan(models.Model):
    _inherit = "route.plan"

    vehicle_closing_ids = fields.One2many("route.vehicle.closing", "plan_id", string="Vehicle Closings")
    vehicle_closing_count = fields.Integer(string="Vehicle Closings", compute="_compute_vehicle_closing_stats", store=False)

    def _compute_vehicle_closing_stats(self):
        for rec in self:
            closings = rec.vehicle_closing_ids.sorted(key=lambda closing: closing.id, reverse=True)
            rec.vehicle_closing_count = len(closings)

    def _get_active_vehicle_closing(self):
        self.ensure_one()
        return self.vehicle_closing_ids.sorted(key=lambda closing: closing.id, reverse=True)[:1]

    def action_open_vehicle_closing(self):
        self.ensure_one()
        if not self.vehicle_id:
            raise UserError(_("Please select a vehicle first."))
        if not getattr(self.vehicle_id, "stock_location_id", False):
            raise UserError(_("Please set the vehicle stock location first."))

        closing = self._get_active_vehicle_closing()
        if not closing:
            closing = self.env["route.vehicle.closing"].create({
                "plan_id": self.id,
                "company_id": self.env.company.id,
                "note": _("End-of-day vehicle closing. Count the physical stock on the vehicle and compare it with the system stock snapshot."),
            })
            closing.action_refresh_snapshot()
        return closing._open_form_action()

