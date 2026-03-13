{
    'name': 'Route Core',
    'version': '19.0.1.0',
    'summary': 'Core module for route distribution',
    'author': 'Yasser',
    'category': 'Sales',
    'license': 'LGPL-3',
    'depends': ['base', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        'data/store_sequence.xml',
        'data/route_sequence.xml',
        'views/store_views.xml',
        'views/route_views.xml',
    ],
    'installable': True,
    'application': True,
}
