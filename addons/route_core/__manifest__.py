{
    "name": "Route Core",
    "version": "19.0.1.0.0",
    "summary": "Sales representative route/visit management",
    "description": "Custom route visit workflow for sales representatives.",
    "category": "Sales",
    "author": "Custom",
    "license": "LGPL-3",
    "depends": ["base", "sale"],
    "data": [
        "security/ir.model.access.csv",
        "views/route_visit_views.xml",
        "wizard/route_visit_end_wizard_views.xml",
    ],
    "installable": True,
    "application": True,
}
