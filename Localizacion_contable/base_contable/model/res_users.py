# -*- coding: utf-8 -*-

from odoo import fields, models, api, exceptions



class ResUsers(models.Model):
    _inherit = 'res.users'


    x_llevar_borra_fact=fields.Selection([('no', 'No'),('si', 'Si')],default="no")