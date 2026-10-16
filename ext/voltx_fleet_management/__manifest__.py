{
    # Module Information
    "name": "Fleet_vehicle_management",
    "category": "Fleet ",
    "version": "19.0.1.1",
    "license": "LGPL-3",
    "summary": """Flota y gestion de conductores""",
    "sequence": 1,
    "author": "Silicon Valley latamn , Colaborador:Ing.Marilyn Millan",
    "website": "www.siliconvalleyve.com",
    "depends": ["base","fleet", "contacts", "account", "base_contable"],
    "data": [
        #"security/ir.model.access.csv",
        #"views/res_partner_view.xml",
        "views/fleet_vehicle_view.xml",
        #"views/fleet_vehicle_contract_view.xml",
        #"views/fleet_vehicle_contract_line_view.xml",
    ],
    "images": ["static/description/icon.jpg"],


    "installable": True,
    "application": True,
}

# -*- coding: utf.8 -*-


