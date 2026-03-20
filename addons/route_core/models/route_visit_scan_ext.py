from odoo import fields, models, _
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _inherit = "route.visit"

    scan_barcode_input = fields.Char(
        string="Scan Barcode",
        copy=False,
    )
    last_scanned_barcode = fields.Char(
        string="Last Scanned Barcode",
        readonly=True,
        copy=False,
    )

    def _get_scan_source_location(self):
        self.ensure_one()
        return self.source_location_id or self.vehicle_id.stock_location_id

    def _get_lot_expiry_date(self, lot):
        self.ensure_one()
        if not lot:
            return False
        for field_name in ("expiration_date", "life_date", "use_date"):
            if field_name in lot._fields and lot[field_name]:
                return fields.Date.to_date(lot[field_name])
        return False

    def _find_available_lot_from_code(self, lot_code):
        self.ensure_one()
        lot_code = (lot_code or "").strip()
        if not lot_code:
            raise UserError(_("Please scan or enter a lot/serial code first."))

        source_location = self._get_scan_source_location()
        if not source_location:
            raise UserError(_("No source location is available for this visit."))

        Lot = self.env["stock.lot"]
        Quant = self.env["stock.quant"]

        lot = Lot.search([("name", "=", lot_code)], limit=1)
        if not lot:
            raise UserError(_("No lot/serial was found with code '%s'.") % lot_code)

        quant = Quant.search(
            [
                ("location_id", "child_of", source_location.id),
                ("lot_id", "=", lot.id),
                ("quantity", ">", 0),
            ],
            limit=1,
        )
        if not quant:
            raise UserError(
                _("Lot '%s' is not currently available in the van stock.")
                % lot.display_name
            )
        return lot

    def _find_available_lots_for_product(self, product):
        self.ensure_one()
        source_location = self._get_scan_source_location()
        if not source_location or not product:
            return self.env["stock.lot"]

        quants = self.env["stock.quant"].search(
            [
                ("location_id", "child_of", source_location.id),
                ("product_id", "=", product.id),
                ("lot_id", "!=", False),
                ("quantity", ">", 0),
            ]
        )
        return quants.mapped("lot_id")

    def _get_packaging_qty_field_name(self, packaging):
        """
        Odoo 19 simplified UoM/Packaging, and field names may differ by edition/customization.
        We try the common quantity field names in a safe order.
        """
        self.ensure_one()
        if not packaging:
            return False
        for field_name in ("qty", "quantity", "contained_qty"):
            if field_name in packaging._fields:
                return field_name
        return False

    def _get_packaging_uom_field_name(self, packaging):
        """
        Try common field names used to point to the packaging unit/reference unit.
        """
        self.ensure_one()
        if not packaging:
            return False
        for field_name in ("uom_id", "unit_id"):
            if field_name in packaging._fields:
                return field_name
        return False

    def _get_packaging_qty(self, packaging):
        self.ensure_one()
        if not packaging:
            return 0.0
        qty_field = self._get_packaging_qty_field_name(packaging)
        if not qty_field:
            return 0.0
        return packaging[qty_field] or 0.0

    def _get_packaging_uom(self, packaging, product=False):
        self.ensure_one()
        if not packaging:
            return product.uom_id if product else False
        uom_field = self._get_packaging_uom_field_name(packaging)
        if uom_field and packaging[uom_field]:
            return packaging[uom_field]
        return product.uom_id if product else False

    def _find_product_packaging_by_barcode(self, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode:
            return False

        # Safe guard: if packaging model is not loaded in this database,
        # do not break the scan flow.
        if "product.packaging" not in self.env:
            return False

        Packaging = self.env["product.packaging"]
        domain = [("barcode", "=", barcode)]

        if "company_id" in Packaging._fields:
            domain = [
                ("barcode", "=", barcode),
                "|",
                ("company_id", "=", False),
                ("company_id", "=", self.company_id.id),
            ]

        return Packaging.search(domain, limit=1)

    def _resolve_scanned_barcode(self, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode:
            raise UserError(_("Please enter or scan a barcode first."))

        product = self.env["product.product"].search(
            [("barcode", "=", barcode)],
            limit=1,
        )
        if product:
            return {
                "product": product,
                "scan_type": "piece",
                "scan_type_label": _("Piece Barcode"),
                "packaging": False,
                "default_scan_qty": 1.0,
                "default_scanned_uom": product.uom_id,
            }

        packaging = self._find_product_packaging_by_barcode(barcode)
        if packaging and packaging.product_id:
            packaging_qty = self._get_packaging_qty(packaging)
            if packaging_qty <= 0:
                raise UserError(
                    _(
                        "Packaging '%(packaging)s' has no valid quantity configured."
                    )
                    % {"packaging": packaging.display_name}
                )

            packaging_uom = self._get_packaging_uom(packaging, packaging.product_id)
            if not packaging_uom:
                raise UserError(
                    _(
                        "Packaging '%(packaging)s' has no valid unit configured."
                    )
                    % {"packaging": packaging.display_name}
                )

            return {
                "product": packaging.product_id,
                "scan_type": "box",
                "scan_type_label": _("Box Barcode"),
                "packaging": packaging,
                "default_scan_qty": packaging_qty,
                "default_scanned_uom": packaging_uom,
            }

        raise UserError(_("No product was found with barcode '%s'.") % barcode)

    def _is_product_tracked_by_lot(self, product):
        self.ensure_one()
        if not product:
            return False
        tracking_value = getattr(product, "tracking", "none") or "none"
        return tracking_value in ("lot", "serial")

    def _resolve_product_active_lot(self, product, active_lot=False):
        self.ensure_one()
        if not product:
            return False

        if not self._is_product_tracked_by_lot(product):
            return False

        if active_lot:
            if active_lot.product_id != product:
                raise UserError(
                    _(
                        "The scanned product does not belong to the active lot.\n\n"
                        "Active Lot: %(lot)s\n"
                        "Lot Product: %(lot_product)s\n"
                        "Scanned Product: %(barcode_product)s\n\n"
                        "Please clear the current lot first, then scan/select the correct lot for this product."
                    )
                    % {
                        "lot": active_lot.display_name,
                        "lot_product": active_lot.product_id.display_name,
                        "barcode_product": product.display_name,
                    }
                )
            return active_lot

        available_lots = self._find_available_lots_for_product(product)
        if not available_lots:
            raise UserError(
                _("Tracked product '%s' has no available lot in the van stock.")
                % product.display_name
            )

        if len(available_lots) == 1:
            return available_lots[:1]

        raise UserError(
            _(
                "Product '%s' has more than one available lot in the van stock. "
                "Please scan/select the lot first."
            )
            % product.display_name
        )

    def _is_product_available_in_vehicle(self, product):
        self.ensure_one()
        source_location = self._get_scan_source_location()
        if not source_location or not product:
            return False

        quant = self.env["stock.quant"].search(
            [
                ("location_id", "child_of", source_location.id),
                ("product_id", "=", product.id),
                ("quantity", ">", 0),
            ],
            limit=1,
        )
        return bool(quant)

    def _get_vehicle_available_qty_for_scan_product(self, product):
        self.ensure_one()
        source_location = self._get_scan_source_location()
        if not source_location or not product:
            return 0.0

        quants = self.env["stock.quant"].search(
            [
                ("location_id", "child_of", source_location.id),
                ("product_id", "=", product.id),
            ]
        )
        return sum(quants.mapped("quantity"))

    def _find_visit_line_for_product(self, product):
        self.ensure_one()
        return self.line_ids.filtered(lambda l: l.product_id == product)[:1]

    def _prepare_visit_line_from_scan(self, product, counted_increase):
        self.ensure_one()
        return {
            "visit_id": self.id,
            "company_id": self.company_id.id,
            "product_id": product.id,
            "previous_qty": 0.0,
            "counted_qty": counted_increase,
            "unit_price": product.lst_price or 0.0,
            "vehicle_available_qty": self._get_vehicle_available_qty_for_scan_product(
                product
            ),
        }

    def _get_scan_counted_increase(self, product, scan_qty=1.0, scanned_uom=False):
        self.ensure_one()
        if not product:
            raise UserError(_("Product is required."))
        if scan_qty <= 0:
            raise UserError(_("Quantity must be greater than zero."))

        base_uom = product.uom_id
        scanned_uom = scanned_uom or base_uom

        try:
            return scanned_uom._compute_quantity(scan_qty, base_uom)
        except Exception as e:
            raise UserError(
                _(
                    "Could not convert the scanned quantity from the selected UoM "
                    "to the product base UoM.\n\n%s"
                )
                % str(e)
            )

    def _process_scanned_barcode(
        self,
        barcode,
        scan_qty=1.0,
        scanned_uom=False,
        active_lot=False,
    ):
        self.ensure_one()
        RouteVisitLine = self.env["route.visit.line"]

        if self.visit_process_state not in ("checked_in", "counting", "reconciled"):
            raise UserError(
                _(
                    "Barcode scanning is only allowed when the visit is Checked In, "
                    "Counting, or Reconciled."
                )
            )

        if not self.vehicle_id:
            raise UserError(_("Please set a vehicle before scanning."))
        if not self.vehicle_id.stock_location_id:
            raise UserError(
                _("The selected vehicle does not have a Vehicle Stock Location.")
            )

        self._sync_source_location_from_vehicle()
        if not self.source_location_id:
            raise UserError(_("No source location is available for this visit."))

        scan_info = self._resolve_scanned_barcode(barcode)
        product = scan_info["product"]

        effective_scan_qty = scan_qty
        effective_scanned_uom = scanned_uom or scan_info.get("default_scanned_uom")

        if (
            scan_info.get("scan_type") == "box"
            and not scanned_uom
            and scan_qty == 1.0
        ):
            effective_scan_qty = scan_info.get("default_scan_qty") or 1.0

        counted_increase = self._get_scan_counted_increase(
            product,
            scan_qty=effective_scan_qty,
            scanned_uom=effective_scanned_uom,
        )

        if not self._is_product_available_in_vehicle(product):
            raise UserError(
                _("Product '%s' is not currently available in the van stock.")
                % product.display_name
            )

        resolved_lot = self._resolve_product_active_lot(product, active_lot=active_lot)
        resolved_expiry_date = (
            self._get_lot_expiry_date(resolved_lot) if resolved_lot else False
        )

        line = self._find_visit_line_for_product(product)
        if line:
            line.write(
                {
                    "counted_qty": (line.counted_qty or 0.0) + counted_increase,
                    "vehicle_available_qty": self._get_vehicle_available_qty_for_scan_product(
                        product
                    ),
                }
            )
        else:
            line = RouteVisitLine.create(
                [self._prepare_visit_line_from_scan(product, counted_increase)]
            )

        self.last_scanned_barcode = (barcode or "").strip()

        if self.visit_process_state == "checked_in":
            self.visit_process_state = "counting"

        return {
            "line": line,
            "product": product,
            "scan_type": scan_info["scan_type"],
            "scan_type_label": scan_info["scan_type_label"],
            "counted_increase": counted_increase,
            "base_uom": product.uom_id,
            "used_uom": effective_scanned_uom or product.uom_id,
            "resolved_lot": resolved_lot,
            "resolved_expiry_date": resolved_expiry_date,
            "packaging": scan_info.get("packaging"),
            "effective_scan_qty": effective_scan_qty,
        }

    def action_scan_barcode_input(self):
        for rec in self:
            rec._process_scanned_barcode(rec.scan_barcode_input, scan_qty=1.0)
            rec.scan_barcode_input = False
        return True

    def action_open_scan_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Scan Barcode"),
            "res_model": "route.visit.scan.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_visit_id": self.id,
                "default_quantity": 1.0,
                "default_scan_mode": "count",
            },
        }
