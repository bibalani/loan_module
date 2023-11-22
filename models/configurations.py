# -*- coding: utf-8 -*-

from odoo import models, fields, api

class Configuration(models.Model):
    _name = "loan.config"

    upload_fields = fields.One2many(comodel_name='loan.upload.type', inverse_name='config_id', string='Upload Fields')


class UploadType(models.Model):
    _name = 'loan.upload.type'

    name = fields.Char(string='name')
    config_id = fields.Many2one(comodel_name='loan.config')