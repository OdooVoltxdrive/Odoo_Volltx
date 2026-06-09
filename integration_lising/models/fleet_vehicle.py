# See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    device = fields.Char("Dispositivo")
    api_fecha_inicio = fields.Date(string="API Fecha Inicio Contrato", copy=False)
    api_total_cuotas = fields.Integer(string="API Total Cuotas", copy=False)
    api_precio_cuota = fields.Float(string="API Precio Cuota", copy=False)

    
    @api.model_create_multi
    def create(self, vals_list):
        # 1. Creamos el vehículo primero de forma nativa
        vehicles = super(FleetVehicle, self).create(vals_list)

        # 2. Iteramos los vehículos creados para generar su contrato automático
        for vehicle in vehicles:
            # Validamos que vengan los datos mínimos obligatorios del contrato
            if vehicle.api_cuotas_totales and vehicle.api_monto_recurrente:
                
                # Definimos la fecha que usaremos (la que viene de la API o la de hoy si no viene ninguna)
                fecha_contrato = vehicle.api_contract_date or fields.Date.today()
                
                # Preparamos los valores para el nuevo contrato de este vehículo
                contract_vals = {
                    "vehicle_id": vehicle.id,
                    "driver_id": vehicle.driver_id.id if vehicle.driver_id else False,
                    
                    # Seteamos ambos campos con la misma fecha para que Odoo calcule correctamente la vigencia
                    "date": fecha_contrato,       # Fecha de contrato
                    "date_start": fecha_contrato, # Fecha de inicio del contrato 🏁
                    
                    # Campos personalizados que añadiste
                    "cuotas_totales": vehicle.api_cuotas_totales,
                    "monto_recurrente": vehicle.api_monto_recurrente,
                }
                
                # Creamos el contrato directamente
                self.env["fleet.vehicle.log.contract"].create(contract_vals)
                
        return vehicles