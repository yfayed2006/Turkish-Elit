{
    "name": "Route Core",
    "version": "19.0.1.0.0",
    "summary": "Route system base module",
    "description": "Base module for route system",
    "author": "Yasser Fayed",
    "license": "LGPL-3",
    "category": "Sales",
    "depends": ["base", "sale_management"],
    "data": [
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "views/route_visit_views.xml",
        "wizard/route_visit_end_wizard_views.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
