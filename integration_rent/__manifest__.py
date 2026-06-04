{
    # Module Information
    "name": "Fleet Rental Vehicle voltx drive",
    "category": "Fleet Rent",
    "version": "19.0",
    "license": "LGPL-3",
    "summary": """Sistema de gestion de leasing""",
    "sequence": 1,
    "author": "Silicon Valley latamn , Colaborador:Ing.Marilyn Millan",
    "website": "www.siliconvalleyve.com",
    "depends": ["base","fleet", "contacts"],
    "data": [
        #"security/ir.model.access.csv",
        "views/res_partner_view.xml",
    ],
    "images": ["static/description/icon.jpg"],
    "assets": {
        #"web.assets_backend": [
            #"fleet_rent/static/src/css/fleet_rent.scss",
            #"fleet_rent/static/src/css/rent_order.css",
        #],
    },


    'demo': [],
    'license': 'LGPL-3',
    'application': True,
}


