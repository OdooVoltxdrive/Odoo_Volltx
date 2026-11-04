from odoo import models, fields, api


class FleetVehicleDriverHistory(models.Model):
    _name = 'fleet.vehicle.driver.history'
    _description = 'Historial de Conductores Asignados al Vehículo'
    _order = 'date_start desc, id desc'

    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehículo',
        required=True,
        ondelete='cascade',
        index=True
    )
    driver_id = fields.Many2one(
        'res.partner',
        string='Conductor',
        required=True,
        index=True
    )
    date_start = fields.Date(
        string='Fecha de Ingreso',
        required=True,
        default=fields.Date.today
    )
    date_end = fields.Date(
        string='Fecha Fin'
    )
    tz = fields.Selection(
        related='driver_id.tz',
        string='Zona Horaria',
        readonly=True,
        store=True,
        help="Zona horaria configurada en la ficha del conductor"
    )
    state = fields.Selection([
        ('active', 'Activo'),
        ('closed', 'Finalizado')
    ], string='Estado', compute='_compute_state', store=True)

    @api.depends('date_end')
    def _compute_state(self):
        today = fields.Date.today()
        for record in self:
            if not record.date_end or record.date_end > today:
                record.state = 'active'
            else:
                record.state = 'closed'