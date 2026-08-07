# -*- coding: utf-8 -*-
{
    'name': "Módulo base localizacion contable  19",

    'summary': """Módulo base localizacion contable  19""",

    'description': """
       Módulo base localizacion contable  18
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
        'sale',
        'purchase',
        'stock_account',
        'sale_stock',
        ],

    # always loaded
    'data': [
        'vista/account_tax_views.xml',
        'vista/account_journal_views.xml',
        'vista/ir_sequence_inherit.xml',
        'vista/res_partner_views.xml',
        'vista/res_company_inherit.xml',
        'vista/res_users.xml',
        'vista/account_move_views.xml',###
        'wizard/pago.xml',
        'vista/modo_pago_view.xml',
        'vista/product_inherit_views.xml',
        'vista/account_paiment_register_view.xml',
        'vista/sale_inherit.xml',
        'vista/purchase_inherit.xml',
        'wizar_report_igtf/wizard.xml',
        'wizar_report_igtf/reporte_view.xml',
        'security/ir.model.access.csv',
        
        #'vista/stock_valuation_layer_base.xml',

        ##'data/data.xml',
    ],
    'application': True,
    'license': 'OEEL-1',
}
