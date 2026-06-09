# See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    device = fields.Char("Dispositivo")
    api_contract_date = fields.Date(string="Fecha del Contrato (API)", copy=False)
    api_cuotas_totales = fields.Integer(string="Cantidad de Cuotas (API)", copy=False)
    api_monto_recurrente = fields.Float(string="Monto Recurrente (API)", copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        # 1. Creamos el vehículo primero de forma nativa
        vehicles = super(FleetVehicle, self).create(vals_list)

        # 2. Iteramos los vehículos creados para generar su contrato automático
        for vehicle in vehicles:
            if vehicle.api_cuotas_totales and vehicle.api_monto_recurrente:
                
                fecha_contrato = vehicle.api_contract_date or fields.Date.today()
                
                contract_vals = {
                    "vehicle_id": vehicle.id,
                    "driver_id": vehicle.driver_id.id if vehicle.driver_id else False,
                    "date": fecha_contrato,
                    "date_start": fecha_contrato,
                    
                    # AQUÍ: Mapeamos los campos 'api_' a los campos reales del contrato corregido
                    "total_cuotas": vehicle.api_cuotas_totales,
                    "precio_cuota": vehicle.api_monto_recurrente,
                }
                
                # Creamos el contrato directamente
                self.env["fleet.vehicle.log.contract"].create(contract_vals)
                
        return vehicles