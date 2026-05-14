from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RouteOutletProspectApprovalWizard(models.TransientModel):
    _name = "route.outlet.prospect.approval.wizard"
    _description = "Potential Customer Approval Setup"

    prospect_id = fields.Many2one("route.outlet.prospect", string="Potential Customer", required=True, ondelete="cascade")
    company_id = fields.Many2one("res.company", string="Company", related="prospect_id.company_id", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Currency", related="prospect_id.currency_id", readonly=True)
    outlet_name = fields.Char(string="Outlet Name", related="prospect_id.name", readonly=True)
    salesperson_id = fields.Many2one("res.users", string="Salesperson", related="prospect_id.salesperson_id", readonly=True)

    outlet_operation_mode = fields.Selection(
        [("direct_sale", "Direct Sale"), ("consignment", "Consignment")],
        string="Outlet Operation Mode",
        required=True,
        default="direct_sale",
    )
    direct_sale_pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Direct Sale Pricelist",
        ondelete="set null",
        help="Pricelist that will be used automatically on Direct Sale Orders for this outlet.",
    )

    consignment_stock_location_mode = fields.Selection(
        [("auto_create", "Create Outlet Stock Location Automatically"), ("select_existing", "Use Existing Stock Location")],
        string="Consignment Stock Location",
        default="auto_create",
    )
    stock_location_id = fields.Many2one(
        "stock.location",
        string="Existing Stock Location",
        domain="[('usage', '=', 'internal'), ('company_id', 'in', [False, company_id])]",
        ondelete="set null",
    )
    shelf_credit_limit_amount = fields.Monetary(
        string="Shelf Credit Limit",
        currency_field="currency_id",
        default=0.0,
        help="Maximum allowed value of goods kept on the outlet shelf for consignment outlets.",
    )
    active_stock_tracking = fields.Boolean(string="Active Stock Tracking", default=True)
    consignment_commission_mode = fields.Selection(
        [("fixed_rate", "Fixed Commission %"), ("category_rate", "Category Commission by Product Category")],
        string="Consignment Commission Type",
        default="category_rate",
        required=True,
    )
    default_commission_rate = fields.Float(
        string="Default Commission %",
        digits=(16, 2),
        default=20.0,
        help="Fallback commission percentage. It is also used when loading category lines.",
    )
    category_commission_line_ids = fields.One2many(
        "route.outlet.prospect.approval.wizard.line",
        "wizard_id",
        string="Category Commission Rules",
    )

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        prospect_id = self.env.context.get("default_prospect_id")
        prospect = self.env["route.outlet.prospect"].browse(prospect_id).exists() if prospect_id else self.env["route.outlet.prospect"]
        if prospect:
            vals.setdefault("prospect_id", prospect.id)
            vals.setdefault("outlet_operation_mode", prospect.outlet_operation_mode or "direct_sale")
            if prospect.outlet_operation_mode == "consignment":
                vals.setdefault("consignment_commission_mode", "category_rate")
        outlet_model = self.env["route.outlet"]
        outlet_default_fields = [
            field_name
            for field_name in [
                "default_commission_rate",
                "commission_rate",
                "consignment_stock_location_mode",
                "active_stock_tracking",
                "shelf_credit_limit_amount",
            ]
            if field_name in outlet_model._fields
        ]
        outlet_defaults = outlet_model.default_get(outlet_default_fields) if outlet_default_fields else {}
        vals.setdefault("default_commission_rate", outlet_defaults.get("default_commission_rate") or outlet_defaults.get("commission_rate") or 20.0)
        vals.setdefault("consignment_stock_location_mode", outlet_defaults.get("consignment_stock_location_mode") or "auto_create")
        vals.setdefault("active_stock_tracking", outlet_defaults.get("active_stock_tracking", True))
        vals.setdefault("shelf_credit_limit_amount", outlet_defaults.get("shelf_credit_limit_amount") or 0.0)
        if not vals.get("direct_sale_pricelist_id"):
            pricelist = self.env["product.pricelist"].search([], limit=1)
            if pricelist:
                vals["direct_sale_pricelist_id"] = pricelist.id
        return vals

    @api.onchange("outlet_operation_mode")
    def _onchange_outlet_operation_mode(self):
        for wizard in self:
            if wizard.outlet_operation_mode == "consignment":
                wizard.direct_sale_pricelist_id = False
                if not wizard.consignment_commission_mode:
                    wizard.consignment_commission_mode = "category_rate"
                if not wizard.consignment_stock_location_mode:
                    wizard.consignment_stock_location_mode = "auto_create"
            else:
                wizard.consignment_commission_mode = "fixed_rate"
                wizard.category_commission_line_ids = [(5, 0, 0)]
                wizard.shelf_credit_limit_amount = 0.0
                wizard.stock_location_id = False

    @api.onchange("consignment_commission_mode", "default_commission_rate")
    def _onchange_consignment_commission_mode(self):
        for wizard in self:
            if wizard.outlet_operation_mode != "consignment" or wizard.consignment_commission_mode != "category_rate":
                continue
            if not wizard.category_commission_line_ids:
                wizard.category_commission_line_ids = wizard._prepare_category_line_commands()

    def _prepare_category_line_commands(self):
        self.ensure_one()
        categories = self.env["product.category"].search([], order="complete_name, id")
        default_rate = self.default_commission_rate or 0.0
        return [(0, 0, {"category_id": category.id, "commission_rate": default_rate, "active": True}) for category in categories]

    def action_load_categories(self):
        self.ensure_one()
        existing_category_ids = set(self.category_commission_line_ids.mapped("category_id").ids)
        commands = []
        for category in self.env["product.category"].search([], order="complete_name, id"):
            if category.id in existing_category_ids:
                continue
            commands.append((0, 0, {"category_id": category.id, "commission_rate": self.default_commission_rate or 0.0, "active": True}))
        self.write({
            "outlet_operation_mode": "consignment",
            "consignment_commission_mode": "category_rate",
            "category_commission_line_ids": commands,
        })
        return self._action_reopen()

    def _action_reopen(self):
        self.ensure_one()
        view = self.env.ref("route_core.view_route_outlet_prospect_approval_wizard_form", raise_if_not_found=False)
        return {
            "type": "ir.actions.act_window",
            "name": _("Approve Potential Customer"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [(view.id, "form")] if view else [(False, "form")],
            "target": "new",
            "context": dict(self.env.context, default_prospect_id=self.prospect_id.id),
        }

    def _validate_commercial_setup(self):
        self.ensure_one()
        if not self.prospect_id:
            raise UserError(_("Potential customer was not found."))
        if self.prospect_id.state != "submitted":
            raise UserError(_("Only submitted potential customers can be approved."))
        if self.outlet_operation_mode == "direct_sale":
            if not self.direct_sale_pricelist_id:
                raise ValidationError(_("Please choose the Direct Sale Pricelist before approval."))
            return
        if (self.default_commission_rate or 0.0) < 0.0 or (self.default_commission_rate or 0.0) > 100.0:
            raise ValidationError(_("Default commission percentage must be between 0 and 100."))
        if (self.shelf_credit_limit_amount or 0.0) < 0.0:
            raise ValidationError(_("Shelf credit limit cannot be negative."))
        if self.consignment_stock_location_mode == "select_existing" and not self.stock_location_id:
            raise ValidationError(_("Please choose the existing stock location for this consignment outlet."))
        if self.consignment_commission_mode == "category_rate":
            if not self.category_commission_line_ids:
                self.write({"category_commission_line_ids": self._prepare_category_line_commands()})
            bad_lines = self.category_commission_line_ids.filtered(lambda line: line.active and ((line.commission_rate or 0.0) < 0.0 or (line.commission_rate or 0.0) > 100.0))
            if bad_lines:
                raise ValidationError(_("Every category commission percentage must be between 0 and 100."))

    def _get_commercial_vals(self):
        self.ensure_one()
        vals = {"outlet_operation_mode": self.outlet_operation_mode}
        if self.outlet_operation_mode == "direct_sale":
            vals["direct_sale_pricelist_id"] = self.direct_sale_pricelist_id.id if self.direct_sale_pricelist_id else False
            return vals
        vals.update({
            "consignment_stock_location_mode": self.consignment_stock_location_mode or "auto_create",
            "stock_location_id": self.stock_location_id.id if self.stock_location_id else False,
            "shelf_credit_limit_amount": self.shelf_credit_limit_amount or 0.0,
            "active_stock_tracking": self.active_stock_tracking,
            "consignment_commission_mode": self.consignment_commission_mode or "fixed_rate",
            "consignment_settlement_policy": "net_after_commission",
            "financial_policy": "auto",
            "default_commission_rate": self.default_commission_rate or 0.0,
            "commission_rate": self.default_commission_rate or 0.0,
        })
        return vals

    def _get_commission_line_vals(self):
        self.ensure_one()
        if self.outlet_operation_mode != "consignment" or self.consignment_commission_mode != "category_rate":
            return []
        vals_list = []
        seen = set()
        for line in self.category_commission_line_ids:
            if not line.active or not line.category_id or line.category_id.id in seen:
                continue
            seen.add(line.category_id.id)
            vals_list.append({
                "category_id": line.category_id.id,
                "commission_rate": line.commission_rate or 0.0,
                "active": True,
                "note": line.note or False,
            })
        return vals_list

    def action_confirm_approval(self):
        self.ensure_one()
        self._validate_commercial_setup()
        return self.prospect_id._approve_and_create_outlet_from_setup(
            commercial_vals=self._get_commercial_vals(),
            commission_line_vals=self._get_commission_line_vals(),
        )


class RouteOutletProspectApprovalWizardLine(models.TransientModel):
    _name = "route.outlet.prospect.approval.wizard.line"
    _description = "Potential Customer Category Commission Setup"
    _order = "category_id"

    wizard_id = fields.Many2one("route.outlet.prospect.approval.wizard", string="Wizard", required=True, ondelete="cascade")
    category_id = fields.Many2one("product.category", string="Product Category", required=True, ondelete="cascade")
    commission_rate = fields.Float(string="Commission %", digits=(16, 2), default=0.0, required=True)
    active = fields.Boolean(default=True)
    note = fields.Char(string="Note")
