#!/usr/bin/env python3
"""
Test script to manually run commission sync
Run this from Odoo shell: exec(open('custom_addons/sales_commision_product/test_sync.py').read())
"""
print("=" * 60)
print("Testing Commission Sync")
print("=" * 60)

# Test the sync
print("\n1. Running commission sync...")
result = env['sales.commission.service'].run_commission_sync()
print(f"   Result: {result}")

# Check commission lines
print("\n2. Checking commission lines...")
commission_lines = env['sales.commission.line'].search([])
print(f"   Found {len(commission_lines)} commission lines")

if commission_lines:
    for line in commission_lines:
        print(f"   - ID: {line.id}, Invoice: {line.invoice_id.name}, "
              f"Product: {line.product_id.name}, "
              f"Commission: {line.commission_amount}, "
              f"Rate: {line.commission_rate}%")
else:
    print("   No commission lines found!")
    
    # Debug: Check eligible invoice lines
    print("\n3. Debugging - Checking eligible invoice lines...")
    move_line_model = env['account.move.line']
    invoice_lines = move_line_model.search([
        ('move_id.state', '=', 'posted'),
        ('move_id.move_type', '=', 'out_invoice'),
        ('move_id.payment_state', 'in', ['paid']),
        ('product_id', '!=', False),
        ('display_type', 'not in', ['line_section', 'line_note']),
    ])
    print(f"   Found {len(invoice_lines)} eligible invoice lines")
    
    for line in invoice_lines:
        rate = line.product_id.product_tmpl_id.commission_rate
        print(f"   - Line ID: {line.id}, Invoice: {line.move_id.name}, "
              f"Product: {line.product_id.name}, "
              f"Rate: {rate}, Price: {line.price_subtotal}")

print("\n" + "=" * 60)
print("Test Complete")
print("=" * 60)

