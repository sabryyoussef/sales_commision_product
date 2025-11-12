# Sales Commission by Product Invoice

## Summary
Compute and report sales commissions based on paid customer invoices and credit notes, with commission rates defined per product. The module records detailed commission lines and provides pivot/list/graph reports to analyze payouts per salesperson.

## Features
- Commission rate (`commission_rate`) on `product.template`, visible in the Sales tab.
- `sales.commission.line` model storing commission details per invoice line.
- Automated synchronization that recalculates commissions, removes entries for cancelled/ unpaid invoices, and handles credit notes as negative commissions.
- Reporting menu under Sales → Reporting, offering pivot, tree, and graph views.
- Security group *Sales Commission Manager* plus record rules to restrict regular salespeople.

## Installation
1. Copy the module folder `sales_commission_product` to your `custom_addons` directory.
2. Update your Odoo configuration (`addons_path`) if needed.
3. Upgrade the module:
   ```
   python3 odoo16/odoo-bin --config=/path/to/odoo.conf -u sales_commission_product
   ```
4. Ensure required dependencies (`account`, `sale_management`) are installed.

## Configuration
- Assign commission rates per product template.
- Add users who should access the report to the *Sales Commission Manager* group.
- Verify the scheduled action **Sales Commission Sync** is active (Settings → Technical → Automation).

## Usage
1. Create and post customer invoices; register payments.
2. Optionally run the sync manually via the server action.
3. Open **Sales → Reporting → Commission Report** to review commissions.
4. Drill into the tree view for detail or export pivot data.

## Documentation
- **USER_GUIDE.md** - Full walkthrough of configuration, access management, and usage
- **TROUBLESHOOTING.md** - Comprehensive guide to errors encountered and their fixes

