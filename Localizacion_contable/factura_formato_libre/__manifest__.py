# -*- coding: utf-8 -*-
{
    'name': "Formatos de Factura/NC/ND forma Libre Localizacion V19",

    'summary': """Formatos de Factura/NC/ND forma Libre Localizacion V19""",

    'description': """
       Formatos de Factura/NC/ND forma Libre Localizacion V19.
    """,
    'version': '19.0.1.0.0',
    'author': 'Ing. Darrell Sojo',
    'category': 'Tools',
    'website': 'http://grupoangendar.com/',
    'license': 'LGPL-3',  # Se agrega para cumplir con el estándar de Odoo

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'base_contable'],

    # always loaded
    'data': [
        'formatos/account_move_view.xml',
        'formatos/factura_libre.xml',
        #'vista/account_move_views.xml',
    ],
    'installable': True,   # <-- ¡Línea obligatoria agregada!
    'application': True,
    'auto_install': False,
}