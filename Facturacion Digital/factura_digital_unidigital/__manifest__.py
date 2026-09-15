
# -*- coding: utf-8 -*-

{
        'name': 'Factura Digital Unidigital',
        'version': '19.0.1.0',
        'author': 'Ing. Darrell Sojo',
        'contribuitors': "Darrell Sojo <dsojo.tanfe@gmail.com>",
        'summary': '',
        'description': """""",
        'category': 'Customizations',
        'depends': ['base','account','base_contable','factura_formato_libre','isrl_retention','iva_retention'],
        'data': [
                'views/company_views.xml',
                'views/account_move_views.xml',
                'views/retention_vat_provee_views.xml',
                'views/retention_vat_islr_views.xml',
                
        ],
        'license': 'LGPL-3',
        'installable': True,
        'application': False, # Cámbialo a True solo si quieres que aparezca como "App" principal en los filtros
        'auto_install': False,
                      
}
