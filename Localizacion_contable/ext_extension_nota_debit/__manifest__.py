# -*- coding: utf-8 -*-
{
    'name': "Extencion correccion nota de debito",

    'summary': """Extencion correccion nota de debito""",

    'description': """
       Extencion correccion nota de debito
       Colaborador: Ing. Darrell Sojo
    """,
    'version': '1.0',
    'author': 'INM&LDR Soluciones Tecnologicas',
    'category': 'Extencion correccion nota de debito',

    # any module necessary for this one to work correctly
    'depends': ['base','account','account_debit_note','base_contable'],

    # always loaded
    'data': [
        'vista/wizard_nota_credito.xml',
        'vista/account_move.xml',
    ],
    'application': True,
}
