from datetime import datetime
import pytz
from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError, ValidationError


class FleetWorkShift(models.Model):
    _name = 'fleet.work.shift'
    _description = 'Turnos de Trabajo de Flota'
    _order = 'start_hour, name'

    name = fields.Char(string='Nombre del Turno', required=True, translate=True)
    shift_type = fields.Selection([
        ('morning', 'Mañana (AM)'),
        ('afternoon', 'Tarde (PM)'),
        ('night', 'Noche'),
        ('mixed_12h', 'Mixto / 12 Horas'),
    ], string='Tipo de Turno', default='morning', required=True)

    applies_on = fields.Selection([
        ('all', 'Todos los días'),
        ('weekdays', 'Lunes a Viernes'),
        ('weekends', 'Sábados y Domingos (Fin de Semana)'),
    ], string='Días de Aplicación', default='all', required=True)

    start_hour = fields.Float(string='Hora Inicio', required=True, help="Ejemplo: 6.0 = 06:00, 18.0 = 18:00")
    end_hour = fields.Float(string='Hora Fin', required=True, help="Ejemplo: 14.0 = 14:00, 6.0 = 06:00 (día siguiente)")
    hours_per_day = fields.Float(string='Horas por Día', compute='_compute_hours_per_day', store=True, readonly=False)
    active = fields.Boolean(default=True)

    @api.depends('start_hour', 'end_hour')
    def _compute_hours_per_day(self):
        for record in self:
            if record.end_hour >= record.start_hour:
                record.hours_per_day = record.end_hour - record.start_hour
            else:
                # Cruce de medianoche (ej. de 18:00 a 06:00 = 12h)
                record.hours_per_day = (24.0 - record.start_hour) + record.end_hour

    @api.constrains('start_hour', 'end_hour')
    def _check_hours(self):
        for record in self:
            if not (0.0 <= record.start_hour < 24.0 and 0.0 <= record.end_hour < 24.0):
                raise ValidationError(_("Las horas de inicio y fin deben estar comprendidas entre las 00:00 y las 23:59."))