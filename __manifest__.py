{
    "name": "Sales Commission by Product Invoice",
    "summary": "Compute and report sales commissions per product based on paid invoices.",
    "version": "16.0.1.0.0",
    "author": "Your Company",
    "depends": [
        "account",
        "sale_management",
    ],
    "data": [
        "security/sales_commission_security.xml",
        "security/ir.model.access.csv",
        "data/commission_cron.xml",
        "views/product_views.xml",
        "views/commission_views.xml",
    ],
    "installable": True,
    "application": True,
}
