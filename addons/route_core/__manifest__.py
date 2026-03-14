{
    "name": "Route Core",
    "version": "17.0.1.0.0",
    "summary": "Sales reps route visits management",
    "description": """
Route Core
==========
Manage sales rep visits and link them with sale orders.
    """,
    "author": "Your Name",
    "website": "https://yourwebsite.com",
    "category": "Sales",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "sale_management",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "views/route_visit_views.xml",
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": True,
}
