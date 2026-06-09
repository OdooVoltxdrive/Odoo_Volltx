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

    # 2. El decorador DEBE tener exactamente los mismos nombres que declaraste arriba
    @api.depends("total_cuotas", "precio_cuota")  
    def _compute_monto_total(self):
        """Calcula el valor total multiplicando las cuotas por su monto"""
        for contract in self:
            contract.monto_total_contrato = contract.total_cuotas * contract.precio_cuota