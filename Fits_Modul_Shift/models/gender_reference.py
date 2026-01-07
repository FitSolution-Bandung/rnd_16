from odoo import models, fields

class GenderReference(models.Model):
    _name = 'gender.reference'
    _description = 'Referensi Gender'

    name = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], string='Gender', required=True, unique=True)
