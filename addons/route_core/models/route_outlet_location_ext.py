from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RouteOutlet(models.Model):
    _inherit = "route.outlet"

    stock_location_id = fields.Many2one(
        "stock.location",
        string="Outlet Stock Location",
        domain=[("usage", "=", "internal")],
        ondelete="restrict",
        help="Internal stock location used for this outlet consignment/location mapping.",
    )
    consignment_stock_location_mode = fields.Selection(
        [("auto_create", "Create Automatically"), ("select_existing", "Select Existing")],
        string="Consignment Stock Location Mode",
        default="auto_create",
        help="Choose whether the outlet stock location should be created automatically under the consignment root path or selected from existing internal locations.",
    )
    auto_stock_location_preview = fields.Char(
        string="Auto Stock Location Path",
        compute="_compute_auto_stock_location_preview",
        readonly=True,
    )

    @api.depends(
        "outlet_operation_mode",
        "consignment_stock_location_mode",
        "company_id",
        "name",
        "code",
        "route_city_id",
        "area_id",
    )
    def _compute_auto_stock_location_preview(self):
        for record in self:
            if record.outlet_operation_mode != "consignment" or record.consignment_stock_location_mode != "auto_create":
                record.auto_stock_location_preview = False
                continue
            parts = [record._get_consignment_root_display_name()]
            if record.route_city_id:
                parts.append(record._sanitize_location_segment(record.route_city_id.name))
            if record.area_id:
                parts.append(record._sanitize_location_segment(record.area_id.name))
            parts.append(record._get_outlet_location_leaf_name())
            record.auto_stock_location_preview = " / ".join([part for part in parts if part])

    @api.onchange("outlet_operation_mode")
    def _onchange_consignment_stock_location_mode(self):
        for record in self:
            if record.outlet_operation_mode == "consignment":
                if not record.consignment_stock_location_mode:
                    record.consignment_stock_location_mode = "auto_create"
            else:
                record.consignment_stock_location_mode = "auto_create"
                record.stock_location_id = False

    @api.constrains("outlet_operation_mode", "consignment_stock_location_mode", "stock_location_id")
    def _check_consignment_stock_location_setup(self):
        for record in self:
            if record.outlet_operation_mode != "consignment":
                continue
            if record.consignment_stock_location_mode == "select_existing" and not record.stock_location_id:
                raise ValidationError(_("Please choose Outlet Stock Location or switch Consignment Stock Location Mode to Create Automatically."))

    def _sanitize_location_segment(self, value):
        value = (value or "").strip()
        return value.replace("/", "-") if value else False

    def _get_outlet_location_leaf_name(self):
        self.ensure_one()
        code = (self.code or "").strip()
        name = (self.name or _("New Outlet")).strip()
        if code:
            return f"{code} - {name}"
        return name

    def _get_consignment_root_display_name(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        root = company.route_default_consignment_root_location_id
        if root:
            return root.complete_name or root.display_name or root.name
        warehouse = company.route_default_source_warehouse_id
        if warehouse and warehouse.view_location_id:
            return "%s / %s" % ((warehouse.view_location_id.complete_name or warehouse.view_location_id.display_name or warehouse.view_location_id.name), _("Consignment Outlets"))
        return _("Consignment Outlets")

    def _get_route_default_source_warehouse(self, company):
        warehouse = company.route_default_source_warehouse_id
        if warehouse:
            return warehouse
        return self.env["stock.warehouse"].sudo().search([("company_id", "=", company.id)], limit=1)

    def _get_or_create_consignment_root_location(self, company):
        company = company.sudo()
        root = company.route_default_consignment_root_location_id
        if root and root.exists():
            return root

        warehouse = self._get_route_default_source_warehouse(company)
        parent_location = warehouse.view_location_id if warehouse and warehouse.view_location_id else False
        vals = {
            "name": _("Consignment Outlets"),
            "usage": "view",
            "company_id": company.id,
            "active": True,
        }
        if parent_location:
            vals["location_id"] = parent_location.id
        root = self.env["stock.location"].sudo().create(vals)
        self.env["ir.config_parameter"].sudo().set_param(
            company._route_feature_param_key("default_consignment_root_location_id"),
            str(root.id),
        )
        return root

    def _get_or_create_child_location(self, parent_location, name, usage, company):
        name = self._sanitize_location_segment(name) or _("Undefined")
        domain = [
            ("location_id", "=", parent_location.id),
            ("name", "=", name),
            ("usage", "=", usage),
            ("company_id", "=", company.id),
        ]
        location = self.env["stock.location"].sudo().search(domain, limit=1)
        if location:
            return location
        return self.env["stock.location"].sudo().create({
            "name": name,
            "usage": usage,
            "location_id": parent_location.id,
            "company_id": company.id,
            "active": True,
        })

    def _ensure_auto_consignment_stock_location(self):
        for record in self:
            if record.outlet_operation_mode != "consignment" or record.stock_location_id:
                continue
            company = record.company_id or self.env.company
            root = record._get_or_create_consignment_root_location(company)
            city_name = record.route_city_id.name or record.city or _("No City")
            area_name = record.area_id.name or record.route_area_name or _("No Area")
            city_location = record._get_or_create_child_location(root, city_name, "view", company)
            area_location = record._get_or_create_child_location(city_location, area_name, "view", company)
            leaf_name = record._get_outlet_location_leaf_name()
            outlet_location = record._get_or_create_child_location(area_location, leaf_name, "internal", company)
            record.with_context(skip_route_outlet_stock_sync=True).write({"stock_location_id": outlet_location.id})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_outlet_stock_location_setup()
        return records

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get("skip_route_outlet_stock_sync"):
            self._sync_outlet_stock_location_setup()
        return result

    def _sync_outlet_stock_location_setup(self):
        for record in self:
            if record.outlet_operation_mode != "consignment":
                if record.stock_location_id:
                    record.with_context(skip_route_outlet_stock_sync=True).write({"stock_location_id": False})
                continue
            if record.consignment_stock_location_mode == "auto_create":
                record._ensure_auto_consignment_stock_location()

    def get_stock_location(self):
        self.ensure_one()
        return self.stock_location_id

    def has_stock_location(self):
        self.ensure_one()
        return bool(self.stock_location_id)
