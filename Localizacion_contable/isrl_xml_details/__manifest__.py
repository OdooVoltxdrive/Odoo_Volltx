# -*- coding: utf-8 -*-

{
        'name': 'ISLR Retencion para Venezuela extencion odoo v19',
        'version': '0.1',
        'author': 'Ing. Darrell Sojo',
        'summary': 'ISLR Retention',
        'description': """This model do the retention about taxes in Venezuela.""",
        'category': 'Accounting/Accounting',
        'website': '',
        'images': [],
        'depends': [
            'account',
            'account_accountant',
            'base',
            'product',
            'isrl_retention',
            'base_contable',
            ],
        'data': [
            'security/ir.model.access.csv',
            'views/retention_details.xml',
            ],
        'installable': True,
        'application': True,
        'auto_install': False,
                      
}
