# -*- coding: utf-8 -*-

{
        'name': 'Retenciones de IVA para Venezuela v19',
        'version': '0.1',
        'author': 'Ing. Darrell Sojo / Silicon Valley',
        'summary': 'Retenciones de IVA para Venezuela v19',
        'description': """Retenciones de IVA para Venezuela v19.""",
        'category': 'Accounting/Accounting',
        'website': '',
        'images': [],
        'depends': [
            'base',
            'account',
            'account_accountant',
            'base_contable',
            #'sign',
            ],
        'data': [
            'security/ir.model.access.csv',
            'views/partner_views.xml',
            'views/res_company_inherit.xml',
            'views/account_move_views.xml',
            'views/retention_vat_provee_views.xml',
            'views/retention_vat_cliente_views.xml',
            'report/vat_wh_voucher.xml',            
            ],
        'installable': True,
        'application': True,
        'auto_install': False,
                      
}
