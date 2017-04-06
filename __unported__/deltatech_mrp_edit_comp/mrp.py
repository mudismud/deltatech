# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2015 Deltatech All Rights Reserved
#                    Dorin Hongu <dhongu(@)gmail(.)com       
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo.exceptions import except_orm, Warning, RedirectWarning
from odoo import models, fields, api, _
from odoo.tools.translate import _
from odoo import SUPERUSER_ID, api
import odoo.addons.decimal_precision as dp


class mrp_production(models.Model):
    _inherit = 'mrp.production'

    move_lines = fields.One2many( readonly=False, states={'done': [('readonly', True)]}  ) 
 




    @api.multi
    def write(self,  vals ):
        res = super(mrp_production, self).write(  vals )
        for move in self.move_lines:
            if move.state == 'draft':
                # se de facut o copie a miscarii si trecuta miscarea la la productie la productie 
                move.action_confirm()        
        return res

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
