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

        # Keep this defensive because expiry fields depend on enabled features/modules.
        for field_name in ("expiration_date", "life_date", "use_date"):
            if field_name in lot._fields and lot[field_name]:
                return fields.Date.to_date(lot[field_name])

        return False

    def _find_available_lot_from_barcode(self, barcode):
        self.ensure_one()

        barcode = (barcode or "").strip()
        if not barcode:
            return False

        source_location = self._get_scan_source_location()
        if not source_location:
            return False

        Lot = self.env["stock.lot"]
        Quant = self.env["stock.quant"]

        lot_domain = [("name", "=", barcode)]
        if "barcode" in Lot._fields:
            lot_domain = ["|", ("name", "=", barcode), ("barcode", "=", barcode)]

        candidate_lots = Lot.search(lot_domain)
        if not candidate_lots:
            return False

        quants = Quant.search(
            [
                ("location_id", "child_of", source_location.id),
                ("lot_id", "in", candidate_lots.ids),
                ("quantity", ">", 0),
            ]
        )
        available_lots = quants.mapped("lot_id")

        if not available_lots:
            return False

        if len(available_lots) > 1:
            raise UserError(
                _(
                    "More than one available lot/serial matches barcode '%s' in the vehicle stock. "
                    "Please scan a unique lot/serial barcode."
                )
                % barcode
            )

        return available_lots[:1]

    def _resolve_scanned_barcode(self, barcode):
        self.ensure_one()

        barcode = (barcode or "").strip()
        if not barcode:
            raise UserError(_("Please enter or scan a barcode first."))

        # Phase C1 safe order:
        # 1) keep existing product-barcode behavior untouched
        # 2) then add real lot/serial resolution from available vehicle stock
        product = self.env["product.product"].search(
            [("barcode", "=", barcode)],
            limit=1,
        )
        if product:
            return {
                "product": product,
                "lot": False,
                "expiry_date": False,
                "scan_type": "unit",
                "scan_type_label": _("Product Barcode"),
            }

        lot = self._find_available_lot_from_barcode(barcode)
        if lot:
            return {
                "product": lot.product_id,
                "lot": lot,
                "expiry_date": self._get_lot_expiry_date(lot),
                "scan_type": "lot",
                "scan_type_label": _("Lot / Serial Barcode"),
            }

        raise UserError(_("No product or available lot/serial was found with barcode '%s'.") % barcode)

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
            "vehicle_available_qty": self._get_vehicle_available_qty_for_scan_product(product),
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

    def _process_scanned_barcode(self, barcode, scan_qty=1.0, scanned_uom=False):
        self.ensure_one()

        RouteVisitLine = self.env["route.visit.line"]

        if self.visit_process_state not in ("checked_in", "counting", "reconciled"):
            raise UserError(
                _("Barcode scanning is only allowed when the visit is Checked In, Counting, or Reconciled.")
            )

        if not self.vehicle_id:
            raise UserError(_("Please set a vehicle before scanning."))

        if not self.vehicle_id.stock_location_id:
            raise UserError(_("The selected vehicle does not have a Vehicle Stock Location."))

        self._sync_source_location_from_vehicle()

        if not self.source_location_id:
            raise UserError(_("No source location is available for this visit."))

        scan_info = self._resolve_scanned_barcode(barcode)
        product = scan_info["product"]

        counted_increase = self._get_scan_counted_increase(
            product,
            scan_qty=scan_qty,
            scanned_uom=scanned_uom,
        )

        if not self._is_product_available_in_vehicle(product):
            raise UserError(
                _("Product '%s' is not currently available in the van stock.")
                % product.display_name
            )

        line = self._find_visit_line_for_product(product)

        if line:
            line.write({
                "counted_qty": (line.counted_qty or 0.0) + counted_increase,
                "vehicle_available_qty": self._get_vehicle_available_qty_for_scan_product(product),
            })
        else:
            line = RouteVisitLine.create([self._prepare_visit_line_from_scan(product, counted_increase)])

        self.last_scanned_barcode = (barcode or "").strip()

        if self.visit_process_state == "checked_in":
            self.visit_process_state = "counting"

        return {
            "line": line,
            "product": product,
            "lot": scan_info.get("lot"),
            "expiry_date": scan_info.get("expiry_date"),
            "scan_type": scan_info["scan_type"],
            "scan_type_label": scan_info["scan_type_label"],
            "counted_increase": counted_increase,
            "base_uom": product.uom_id,
            "used_uom": scanned_uom or product.uom_id,
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
