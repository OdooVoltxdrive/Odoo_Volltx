from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    voltx_service_product_id = fields.Many2one(
        'product.product', string='Producto de servicio VoltX (aprobado por contabilidad)',
        check_company=True,
        help='Dejar vacío hasta que contabilidad confirme el producto y su cuenta de ingresos. '
             'Sin esta asignación no se generan facturas con cargo de servicio.',
    )
