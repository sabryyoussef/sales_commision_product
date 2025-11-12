# Troubleshooting Guide - Sales Commission by Product Invoice

This document details all errors encountered during development and their fixes.

---

## Table of Contents

1. [Module Installation Errors](#module-installation-errors)
2. [Commission Sync Issues](#commission-sync-issues)
3. [Report Display Problems](#report-display-problems)
4. [Data Deletion Issues](#data-deletion-issues)
5. [Quick Reference](#quick-reference)

---

## Module Installation Errors

### Error 1: External ID Not Found

**Error Message:**
```
ValueError: External ID not found in the system: sales_commission_product.group_sales_commission_manager
```

**Location:**
- `security/sales_commission_security.xml` (line 19)
- `security/ir.model.access.csv` (lines 2-3)
- `views/commission_views.xml` (line 82)

**Root Cause:**
Module folder name mismatch:
- **Folder name:** `sales_commision_product` (one 's' in commission)
- **References used:** `sales_commission_product` (two 's' in commission)

**Fix:**
Changed all external ID references to match the actual folder name:

```xml
<!-- Before -->
<field name="groups" eval="[(4, ref('sales_commission_product.group_sales_commission_manager'))]"/>

<!-- After -->
<field name="groups" eval="[(4, ref('sales_commision_product.group_sales_commission_manager'))]"/>
```

**Files Modified:**
- `security/sales_commission_security.xml`
- `security/ir.model.access.csv`
- `views/commission_views.xml`

---

## Commission Sync Issues

### Error 2: Invalid Search Domain Fields

**Error Message:**
```
No commission lines created when running scheduled action
```

**Location:**
`models/commission_service.py` (lines 30-46)

**Root Cause:**
Multiple issues in the search domain:
1. Used `parent_state` field (unreliable in Odoo 16)
2. Used `exclude_from_invoice_tab` field (doesn't exist in Odoo 16)
3. Wrong `display_type` check (checked for `False` but it's a string value)

**Original Code:**
```python
invoice_lines = move_line_model.search([
    ("parent_state", "=", "posted"),  # ❌ Unreliable field
    ("move_id.state", "=", "posted"),
    ("move_id.move_type", "=", "out_invoice"),
    ("move_id.payment_state", "in", ["paid"]),
    ("product_id", "!=", False),
    ("display_type", "=", False),  # ❌ Wrong - it's a string, not False
    ("exclude_from_invoice_tab", "=", False),  # ❌ Field doesn't exist
])
```

**Fixed Code:**
```python
invoice_lines = move_line_model.search([
    ("move_id.state", "=", "posted"),  # ✅ Direct field access
    ("move_id.move_type", "=", "out_invoice"),
    ("move_id.payment_state", "in", ["paid"]),
    ("product_id", "!=", False),
    ("display_type", "not in", ["line_section", "line_note"]),  # ✅ Correct check
    # ✅ Removed non-existent field
])
```

**Impact:**
- Before: No invoice lines found → No commission lines created
- After: Invoice lines found correctly → Commission lines created successfully

---

### Error 3: Non-Existent Field Reference

**Error Message:**
```
AttributeError: 'account.move' object has no attribute 'user_id'
```

**Location:**
`models/commission_service.py` (line 65)

**Root Cause:**
Code tried to access `move.user_id` which doesn't exist in Odoo 16. The correct field is `invoice_user_id`.

**Original Code:**
```python
salesperson = move.invoice_user_id or move.user_id or self.env.user  # ❌ user_id doesn't exist
```

**Fixed Code:**
```python
salesperson = move.invoice_user_id or self.env.user  # ✅ Correct field
```

**Impact:**
- Before: Runtime error when trying to get salesperson
- After: Salesperson correctly identified from invoice

---

### Error 4: Missing Error Handling

**Error Message:**
```
Scheduled action crashes silently or times out
```

**Location:**
`models/commission_service.py` - entire `run_commission_sync()` method

**Root Cause:**
- No try/except block to catch errors
- No logging for debugging
- No batch processing for large datasets
- Could cause timeout with many records

**Fix:**
Added comprehensive error handling and optimizations:

```python
@api.model
def run_commission_sync(self):
    """Synchronize commission lines from invoice lines."""
    try:
        # ... sync logic ...
        
        # Create in batches to avoid timeout
        if eligible_map:
            create_vals = list(eligible_map.values())
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
```

**Impact:**
- Before: Crashes break scheduled action, no error visibility
- After: Errors logged, scheduled action continues, batch processing prevents timeouts

---

## Report Display Problems

### Error 5: Commission Lines Not Appearing in Report

**Error Message:**
```
Commission report shows empty or "No data available"
```

**Root Cause:**
Multiple cascading issues:
1. Search domain not finding invoice lines (Error 2)
2. No commission lines created in database
3. Report has no data to display

**Fix:**
Resolved by fixing Error 2 (search domain). Once commission lines are created correctly, they appear in the report automatically.

**Verification:**
```sql
-- Check commission lines exist
SELECT COUNT(*) FROM sales_commission_line;

-- Check totals
SELECT SUM(commission_amount) as total_commission, 
       SUM(line_subtotal) as total_subtotal 
FROM sales_commission_line;
```

---

## Data Deletion Issues

### Error 6: Valid Commission Lines Being Deleted

**Error Message:**
```
Commission lines disappear after running scheduled action
```

**Location:**
`models/commission_service.py` (lines 90-94)

**Root Cause:**
Aggressive deletion logic - deleted commission lines even when invoices were still valid. If a commission line wasn't found in `eligible_map`, it was deleted without checking if the invoice was still eligible.

**Original Code:**
```python
for invoice_line_id, commission_line in existing_map.items():
    line_vals = eligible_map.pop(invoice_line_id, None)
    if not line_vals:
        lines_to_unlink.append(commission_line.id)  # ❌ Deletes without checking!
        continue
```

**Problem:**
- If `eligible_map` was empty (due to search domain issues), ALL commission lines were deleted
- Even valid commissions were removed

**Fixed Code:**
```python
for invoice_line_id, commission_line in existing_map.items():
    line_vals = eligible_map.pop(invoice_line_id, None)
    if not line_vals:
        # ✅ Only delete if invoice is truly invalid
        invoice_line = move_line_model.browse(invoice_line_id)
        if not invoice_line.exists():
            # Invoice line was deleted, remove commission line
            lines_to_unlink.append(commission_line.id)
        else:
            move = invoice_line.move_id
            # ✅ Check if invoice is still valid before deleting
            if (move.state != 'posted' or 
                (move.move_type == 'out_invoice' and move.payment_state != 'paid')):
                lines_to_unlink.append(commission_line.id)
        continue
```

**Impact:**
- Before: Valid commission lines deleted on every sync
- After: Only invalid commission lines deleted (invoices not posted/paid)

---

## Quick Reference

### Common Issues and Solutions

| Issue | Symptom | Solution |
|-------|---------|----------|
| Module won't install | External ID error | Check module name matches folder name |
| No commission lines created | Empty report | Verify search domain fields exist |
| Commission lines deleted | Data disappears after sync | Check deletion logic (Error 6) |
| Timeout errors | Scheduled action fails | Ensure batch processing enabled |
| Wrong salesperson | Incorrect user assigned | Use `invoice_user_id` not `user_id` |

### Verification Queries

**Check eligible invoice lines:**
```sql
SELECT COUNT(*) 
FROM account_move_line aml
JOIN account_move am ON aml.move_id = am.id
WHERE am.state = 'posted' 
  AND am.move_type = 'out_invoice'
  AND am.payment_state = 'paid'
  AND aml.product_id IS NOT NULL
  AND aml.display_type NOT IN ('line_section', 'line_note');
```

**Check commission lines:**
```sql
SELECT id, invoice_id, commission_rate, commission_amount, line_subtotal
FROM sales_commission_line
ORDER BY id;
```

**Check product commission rates:**
```sql
SELECT pt.id, pt.name, pt.commission_rate
FROM product_template pt
WHERE pt.commission_rate > 0;
```

### Testing Checklist

- [ ] Module installs without errors
- [ ] Scheduled action runs successfully
- [ ] Commission lines created for paid invoices
- [ ] Commission lines not deleted when invoice still valid
- [ ] Report displays commission data
- [ ] Totals match expected values (rate × subtotal)

---

## Version History

**Version 16.0.1.0.0** (Current)
- Fixed module name mismatch in external IDs
- Fixed search domain to use correct fields
- Fixed salesperson field reference
- Improved deletion logic to preserve valid commissions
- Added error handling and batch processing

---

## Support

If you encounter issues not covered in this document:

1. Check Odoo logs: `docker logs <odoo-container> --tail 100`
2. Verify database state using SQL queries above
3. Check scheduled action status in Odoo UI
4. Ensure module is upgraded after fixes

---

**Last Updated:** November 12, 2025

