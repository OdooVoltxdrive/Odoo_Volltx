from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    voltx_service_product_id = fields.Many2one(
        'product.product', string='Producto de servicio VoltX (aprobado por contabilidad)',
        check_company=True,
        help='Dejar vacío hasta que contabilidad confirme el producto y su cuenta de ingresos. '
             'Sin esta asignación no se generan facturas con cargo de servicio.',
    )
    voltx_usd_vat_tax_id = fields.Many2one(
        'account.tax', string='IVA USD VoltX (a revisar por un contador)', check_company=True,
        help='Impuesto separado: IVA 16 % no incluido, secuencia anterior al IGTF, '
             'con efecto sobre la base del impuesto siguiente. No modificar el IVA compartido.',
    )
    voltx_igtf_tax_id = fields.Many2one(
        'account.tax', string='IGTF SENIAT VoltX (a revisar por un contador)', check_company=True,
        help='IGTF 3 % no incluido sobre base + IVA, con cuenta de pasivo propia confirmada '
             'por contabilidad. La cuenta QA 2175021 no aprueba una configuración productiva.',
    )
