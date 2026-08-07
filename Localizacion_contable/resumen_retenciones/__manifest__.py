# -*- coding: utf-8 -*-
{
    'name': "Reportes de reumen  de retenciones IVA e ISLR v19",

    'summary': """Reportes de resumen de retenciones V19""",

    'description': """
       Reportes de resumenes de retenciones IVA, e ISLR V19.
    """,
    'version': '15.0',
    'author': 'Ing. Darrell Sojo',
    'category': 'Tools',
    'website': 'dsojo.tanfe@gmail.com',
    'license': 'LGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['base','account','iva_retention','isrl_retention','libro_compra_venta','base_contable'],

    # always loaded
    'data': [
    	'security/ir.model.access.csv',
        'resumen_iva/wizard.xml',
        'resumen_iva/reporte_view.xml',
        ##'resumen_municipal/wizard.xml',
        ##'resumen_municipal/reporte_view.xml',
        'resumen_islr/wizard.xml',
        'resumen_islr/reporte_view.xml',
    ],
    'installable': True,
    'application': True,
    'active':False,
    'auto_install': False,
}
