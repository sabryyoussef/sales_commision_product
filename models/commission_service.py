from odoo import api, fields, models
from odoo.tools import float_compare


class CommissionService(models.Model):
    _name = "sales.commission.service"
    _description = "Sales Commission Computation Service"
    _log_access = False

    last_processed_move_line_id = fields.Many2one(
        comodel_name="account.move.line",
        string="Last Processed Move Line",
        help="Technical field to avoid duplicate commission entries.",
    )

    @api.model
    def _get_service(self):
        service = self.search([], limit=1)
        if not service:
            service = self.create({})
        return service

    @api.model
    def run_commission_sync(self):
        """Synchronize commission lines from invoice lines.
        This method processes paid invoices and creates/updates commission records.
        """
        try:
            self._get_service()  # ensure record exists for backward compatibility
            move_line_model = self.env["account.move.line"]
            commission_line_model = self.env["sales.commission.line"]

            # Search for invoice lines - use move_id.state directly for better reliability
            # Exclude section and note lines (display_type in ['line_section', 'line_note'])
            invoice_lines = move_line_model.search([
                ("move_id.state", "=", "posted"),
                ("move_id.move_type", "=", "out_invoice"),
                ("move_id.payment_state", "in", ["paid"]),
                ("product_id", "!=", False),
                ("display_type", "not in", ["line_section", "line_note"]),
            ])

            # Search for refund lines (credit notes)
            refund_lines = move_line_model.search([
                ("move_id.state", "=", "posted"),
                ("move_id.move_type", "=", "out_refund"),
                ("product_id", "!=", False),
                ("display_type", "not in", ["line_section", "line_note"]),
            ])

            eligible_lines = invoice_lines | refund_lines

            eligible_map = {}
            for line in eligible_lines:
                # Get commission rate from product template
                if not line.product_id or not line.product_id.product_tmpl_id:
                    continue
                commission_rate = line.product_id.product_tmpl_id.commission_rate
                if not commission_rate or commission_rate <= 0:
                    continue

                move = line.move_id
                base_amount = line.price_subtotal
                commission_amount = base_amount * (commission_rate / 100.0)
                if move.move_type == "out_refund":
                    commission_amount *= -1

                # Get salesperson - invoice_user_id is the field in Odoo 16
                salesperson = move.invoice_user_id or self.env.user

                eligible_map[line.id] = {
                    "salesperson_id": salesperson.id,
                    "invoice_id": move.id,
                    "invoice_line_id": line.id,
                    "product_id": line.product_id.id,
                    "quantity": line.quantity,
                    "commission_rate": commission_rate,
                    "commission_amount": commission_amount,
                    "line_subtotal": base_amount,
                    "company_id": move.company_id.id,
                }

            # Get existing commission lines indexed by invoice_line_id
            existing_lines = commission_line_model.search([])
            existing_map = {}
            for line in existing_lines:
                if line.invoice_line_id:
                    existing_map[line.invoice_line_id.id] = line
            
            create_vals = []
            lines_to_unlink = []

            # Process existing lines - update or mark for deletion
            for invoice_line_id, commission_line in existing_map.items():
                line_vals = eligible_map.pop(invoice_line_id, None)
                if not line_vals:
                    # Check if we should delete this commission line
                    # Only delete if the invoice is no longer posted/paid or invoice line doesn't exist
                    invoice_line = move_line_model.browse(invoice_line_id)
                    if not invoice_line.exists():
                        # Invoice line was deleted, remove commission line
                        lines_to_unlink.append(commission_line.id)
                    else:
                        move = invoice_line.move_id
                        # Delete if invoice is not posted, or if it's an invoice that's not paid
                        if (move.state != 'posted' or 
                            (move.move_type == 'out_invoice' and move.payment_state != 'paid')):
                            lines_to_unlink.append(commission_line.id)
                    continue

                updates = {}
                if commission_line.salesperson_id.id != line_vals["salesperson_id"]:
                    updates["salesperson_id"] = line_vals["salesperson_id"]
                if commission_line.invoice_id.id != line_vals["invoice_id"]:
                    updates["invoice_id"] = line_vals["invoice_id"]
                if commission_line.product_id.id != line_vals["product_id"]:
                    updates["product_id"] = line_vals["product_id"]
                uom = commission_line.invoice_line_id.product_uom_id
                qty_differs = False
                if uom and uom.rounding:
                    qty_differs = float_compare(
                        commission_line.quantity,
                        line_vals["quantity"],
                        precision_rounding=uom.rounding,
                    )
                else:
                    qty_differs = float_compare(
                        commission_line.quantity,
                        line_vals["quantity"],
                        precision_digits=6,
                    )
                if qty_differs:
                    updates["quantity"] = line_vals["quantity"]
                if float_compare(commission_line.commission_rate, line_vals["commission_rate"], precision_digits=4):
                    updates["commission_rate"] = line_vals["commission_rate"]

                currency = commission_line.company_currency_id
                if currency and not currency.is_zero(commission_line.commission_amount - line_vals["commission_amount"]):
                    updates["commission_amount"] = line_vals["commission_amount"]
                if currency and not currency.is_zero(commission_line.line_subtotal - line_vals["line_subtotal"]):
                    updates["line_subtotal"] = line_vals["line_subtotal"]
                if commission_line.company_id.id != line_vals["company_id"]:
                    updates["company_id"] = line_vals["company_id"]

                if updates:
                    commission_line.write(updates)

            # Delete obsolete commission lines
            if lines_to_unlink:
                commission_line_model.browse(lines_to_unlink).unlink()

            # Create new commission lines
            if eligible_map:
                create_vals = list(eligible_map.values())
                # Create in batches to avoid timeout with large datasets
                batch_size = 100
                for i in range(0, len(create_vals), batch_size):
                    batch = create_vals[i:i + batch_size]
                    commission_line_model.create(batch)

            return True
        except Exception as e:
            # Log error but don't raise to avoid breaking scheduled action
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error("Error in commission sync: %s", str(e))
            return False

