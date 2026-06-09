{
    # Module Information
    "name": "Fleet_vehicle_leasing",
    "category": "Fleet leasing",
    "version": "19.0.0",
    #"license": "LGPL-3",
    "summary": """Sistema de gestion de leasing""",
    "sequence": 1,
    "author": "Silicon Valley latamn , Colaborador:Ing.Marilyn Millan",
    "website": "www.siliconvalleyve.com",
    "depends": ["base","fleet", "contacts"],
    "data": [
        #"security/ir.model.access.csv",
        "views/res_partner_view.xml",
        "views/fleet_vehicle_view.xml",
        "views/fleet_vehicle_contract_view.xml",
    ],
    "images": ["static/description/icon.jpg"],


    "installable": True,
    "application": True,
}

# -*- coding: utf.8 -*-


