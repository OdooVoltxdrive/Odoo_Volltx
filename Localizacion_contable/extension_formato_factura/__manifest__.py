# -*- coding: utf-8 -*-
{
    'name': "Extension Formato Factura Forma Libre 19",
    'summary': """Extension Formato Factura Forma Libre 19""",
    'description': """
       Extension Formato Factura Forma Libre 19
       Colaborador: Ing. Darrell Sojo
    """,
    'version': '19.0.1.0.0',
    'author': 'Ing. Darrell Sojo',
    'category': 'Tools',
    'license': 'LGPL-3',
    'depends': [
        'base','account','factura_formato_libre',
    ],
    'data': [
        #'formatos/factura_libre_somofit.xml',
        'formatos/facturas_libre_s_bs.xml',
    ],
    'installable': True,
    'application': False, # Cámbialo a True solo si quieres que aparezca como "App" principal en los filtros
    'auto_install': False,
}