{
    'name': 'Voltx Fleet Shifts',
    'version': '19.0.1',
    'summary': 'Gestionar los turnos de los vehículos de la flota y a los distintos conductores',
    'description': """
        Este módulo amplía la aplicación Fleet para permitir la asignación de varios 
        conductores a un mismo vehículo en diferentes turnos y cada uno con su contrato individual. 
        Incluye llevar el control de las liquidaciones.
    """,
    'category': 'Human Resources/Fleet',
    'author': 'Your Company',
    'depends': ['fleet', 'account', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'views/fleet_vehicle_views.xml',
        'views/fleet_vehicle_driver_history_views.xml',
        'views/fleet_vehicle_log_contract_views.xml',
        'views/fleet_weekly_liquidation_views.xml',
        'views/fleet_menus.xml',
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}