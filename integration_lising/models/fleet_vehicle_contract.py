# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class FleetVehicleLogContract(models.Model):
    _inherit = "fleet.vehicle.log.contract"

    # Nuevos campos para capturar los datos del tercero
    total_cuotas = fields.Integer(string="Total de Cuotas")
    precio_cuota = fields.Float(string="Precio de cada Cuota ($)")

    # Campo calculado (opcional pero muy útil) para saber el total del contrato
    monto_total_contrato = fields.Float(
        string="Monto Total ($)", 
        compute="_compute_monto_total", 
        store=True
    )

    # Sobreescribimos el campo nativo 'cost_frequency' para que por defecto sea mensual
    #cost_frequency = fields.Selection(default="monthly")

    @api.depends("cuotas_totales", "monto_recurrent_")  # Corregido a depend en vez de onchange para que funcione también por API
    def _compute_monto_total(self):
        """Calcula el valor total multiplicando las cuotas por su monto"""
        for contract in self:
            contract.monto_total_contrato = contract.cuotas_totales * contract.monto_recurrente