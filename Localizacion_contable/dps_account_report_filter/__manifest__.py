# -*- coding: utf-8 -*-
{
    'name': "Informes financieros de Odoo: Filtro de moneda | Informe contable en múltiples monedas | Informes contables multimoneda (Original)  19",

    'summary': """Informes financieros de Odoo: Filtro de moneda | Informe contable en múltiples monedas | Informes contables multimoneda (Original)  19""",

    'description': """
       Informes financieros de Odoo: Filtro de moneda | Informe contable en múltiples monedas | Informes contables multimoneda (Original)  19
       Colaborador: Ing. Darrell Sojo
    """,
    'version': '18.0',
    'author': 'Ing.Darrell Sojo',
    'category': 'Módulo base localizacion contable  V19',

    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'stock',
        'account',
        'account_accountant',
        'account_debit_note',
        'account_reports',
        ],

    # always loaded
    'data': [
        
    ],
    "assets": {
        "web.assets_backend": [
            "dps_account_report_filter/static/src/components/**/*",
        ],
    },
    'application': True,
    'license': 'OEEL-1',
}
