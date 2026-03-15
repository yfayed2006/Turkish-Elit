{
    "name": "Route Core",
    "version": "19.0.1.0.0",
    "summary": "Sales representative route visits",
    "depends": ["base", "sale", "mail", "stock", "contacts"],
    "data": [
        "security/ir.model.access.csv",
        "data/route_visit_sequence.xml",
        "views/route_area_views.xml",
        "views/res_partner_views.xml",
        "views/route_visit_views.xml",
        "wizard/route_visit_end_wizard_views.xml",
    ],
    "installable": True,
    "application": True,
}
