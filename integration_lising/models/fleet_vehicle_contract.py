# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class FleetVehicleLogContract(models.Model):
    _inherit = "fleet.vehicle.log.contract"

    # 1. Asegúrate de que los campos estén declarados exactamente con estos nombres
    total_cuotas = fields.Integer(string="Total de Cuotas")
    precio_cuota = fields.Float(string="Precio de cada Cuota ($)")
    
    monto_total_contrato = fields.Float(
        string="Monto Total ($)", 
        compute="_compute_monto_total", 
        store=True
    )

    # Nueva pestaña de trazabilidad
    contract_line_ids = fields.One2many(
        "fleet.vehicle.contract.line", "contract_id", string="Plan de Cuotas"
    )

    @api.depends("total_cuotas", "precio_cuota")
    def _compute_monto_total(self):
        """Calcula el valor total: Tarifa Diaria x 30 días x N° de Meses"""
        for contract in self:
            # Multiplicamos el valor diario por 30 para sacar el mes comercial, y luego por los meses totales
            contract.monto_total_contrato = (
                contract.precio_cuota * 30 * contract.total_cuotas
            )