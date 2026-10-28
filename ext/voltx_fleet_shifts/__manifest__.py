{
    'name': 'Voltx Fleet Shifts',
    'version': '19.0.0.7.0',
    'summary': 'Manage fleet vehicle shifts and multiple drivers',
    'description': """
        This module extends the Fleet app to support multiple drivers assigned to a single vehicle
        across different shifts. Includes daily logs and weekly liquidations.
    """,
    'category': 'Human Resources/Fleet',
    'author': 'Your Company',
    'depends': ['fleet', 'account','contacts','base','factura_digital_unidigital',],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_view.xml',
        'views/res_company_views.xml',
        'views/fleet_vehicle_views.xml',
        'views/fleet_vehicle_driver_history_views.xml',
        'views/fleet_vehicle_log_contract_views.xml',
        'views/fleet_weekly_liquidation_views.xml',
        'views/fleet_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
