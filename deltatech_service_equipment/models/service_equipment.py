# -*- coding: utf-8 -*-
# ©  2015-2018 Deltatech
# See README.rst file on addons root folder for license details


from odoo import models, fields, api, _
from odoo.exceptions import except_orm, Warning, RedirectWarning
from odoo.tools import float_compare
import odoo.addons.decimal_precision as dp
import math
from dateutil.relativedelta import relativedelta
from datetime import date, datetime





class service_equipment(models.Model):
    _name = 'service.equipment'
    _description = "Equipment"
    _inherit = 'mail.thread'

    state = fields.Selection([('available', 'Available'), ('installed', 'Installed'),
                              ('backuped', 'Backuped')], default="available", string='Status', copy=False)

    agreement_id = fields.Many2one('service.agreement', string='Contract Service', compute="_compute_agreement_id")
    agreement_type_id = fields.Many2one('service.agreement.type', string='Agreement Type',
                                        related='agreement_id.type_id')
    user_id = fields.Many2one('res.users', string='Responsible', track_visibility='onchange')

    # proprietarul  echipamentului
    partner_id = fields.Many2one('res.partner', string='Customer', related='agreement_id.partner_id', store=True,
                                 readonly=True, help='The owner of the equipment')
    address_id = fields.Many2one('res.partner', string='Location',
                                 readonly=True,  help='The address where the equipment is located')
    # emplacement = fields.Char(string='Emplacement',  readonly=True,
    #                           help='Detail of location of the equipment in working point')

    #install_date = fields.Date(string='Installation Date',  readonly=True)

    # contact_id = fields.Many2one('res.partner', string='Contact Person', track_visibility='onchange',
    #                              domain=[('type', '=', 'contact'), ('is_company', '=', False)])

    name = fields.Char(string='Name', index=True, required=True, copy=False)
    display_name = fields.Char(compute='_compute_display_name')


    total_revenues = fields.Float(string="Total Revenues",
                                  readonly=True)  # se va calcula din suma consumurilor de servicii
    total_costs = fields.Float(string="Total cost", readonly=True)  # se va calcula din suma avizelor

    note = fields.Text(String='Notes')
    start_date = fields.Date(string='Start Date')

    meter_ids = fields.One2many('service.meter', 'equipment_id', string='Meters', copy=True)
    # meter_reading_ids = fields.One2many('service.meter.reading', 'equipment_id', string='Meter Reading',   copy=False) # mai trebuie ??



    type_id = fields.Many2one('service.equipment.type', required=True, string='Type')
    categ_id = fields.Many2one('service.equipment.category', related="type_id.categ_id", string="Category")

    readings_status = fields.Selection([('', 'N/A'), ('unmade', 'Unmade'), ('done', 'Done')], string="Readings Status",
                                       compute="_compute_readings_status", store=True)

    group_id = fields.Many2one('service.agreement.group', string="Service Group")

    @api.model
    def create(self, vals):
        if ('name' not in vals) or (vals.get('name') in ('/', False)):
            sequence = self.env.ref('deltatech_service_equipment.sequence_equipment')
            if sequence:
                vals['name'] = sequence.next_by_id()

        return super(service_equipment, self).create(vals)

    @api.multi
    def write(self, vals):
        if ('name' in vals) and (vals.get('name') in ('/', False)):
            self.ensure_one()
            sequence = self.env.ref('deltatech_service_equipment.sequence_equipment')
            if sequence:
                vals['name'] = sequence.next_by_id()
        return super(service_equipment, self).write(vals)



    @api.multi
    def costs_and_revenues(self):
        for equi in self:
            cost = 0.0
            pickings = self.env['stock.picking'].search([('equipment_id', '=', equi.id), ('state', '=', 'done')])
            for picking in pickings:
                for move in picking.move_lines:
                    move_value = 0.0
                    for quant in move.quant_ids:
                        move_value += quant.cost * quant.qty
                    if move.location_id.usage == 'internal':
                        cost += move_value
                    else:
                        cost -= move_value
            revenues = 0.0
            consumptions = self.env['service.consumption'].search([('equipment_id', '=', equi.id)])
            for consumption in consumptions:
                if consumption.state == 'done':
                    revenues += consumption.currency_id.compute(consumption.price_unit * consumption.quantity,
                                                                self.env.user.company_id.currency_id)

            equi.write({'total_costs': cost,
                        'total_revenues': revenues})

    @api.multi
    def _compute_readings_status(self):
        from_date = date.today() + relativedelta(day=1, months=0, days=0)
        to_date = date.today() + relativedelta(day=1, months=1, days=-1)
        from_date = fields.Date.to_string(from_date)
        to_date = fields.Date.to_string(to_date)

        current_month = [('date', '>=', from_date), ('date', '<=', to_date)]
        for equi in self:
            equi.readings_status = 'done'
            for meter in equi.meter_ids:
                if not meter.last_meter_reading_id:
                    equi.readings_status = 'unmade'
                    break
                if not (from_date <= meter.last_meter_reading_id.date <= to_date):
                    equi.readings_status = 'unmade'
                    break

    # @api.depends('name', 'address_id')  # this definition is recursive
    # def _compute_display_name(self):
    #     if self.address_id:
    #         self.display_name = self.name + ' / ' + self.address_id.name
    #     else:
    #         self.display_name = self.name


    def _compute_agreement_id(self):
        for equipment in self:
            if isinstance(equipment.id, models.NewId):
                return
            agreements = self.env['service.agreement']
            agreement_line = self.env['service.agreement.line'].search([('equipment_id', '=', equipment.id)])
            for line in agreement_line:
                if line.agreement_id.state == 'open':
                    agreements = agreements | line.agreement_id
            if len(agreements) > 1:
                msg = _("Equipment %s assigned to many agreements.")
                equipment.message_post(msg)

            # daca nu e activ intr-un contract poate se gaseste pe un contract ciorna
            if not agreements:
                for line in agreement_line:
                    if line.agreement_id.state == 'draft':
                        agreements = agreements | line.agreement_id

            if len(agreements) > 0:
                equipment.agreement_id = agreements[0]
                equipment.partner_id = agreements[0].partner_id


    @api.multi
    def invoice_button(self):
        invoices = self.env['account.invoice']
        for meter in self.meter_ids:
            for meter_reading in meter.meter_reading_ids:
                if meter_reading.consumption_id and meter_reading.consumption_id.invoice_id:
                    invoices = invoices | meter_reading.consumption_id.invoice_id

        return {
            'domain': "[('id','in', [" + ','.join(map(str, invoices.ids)) + "])]",
            'name': _('Services Invoices'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.invoice',
            'view_id': False,
            'context': "{'type':'out_invoice', 'journal_type': 'sale'}",
            'type': 'ir.actions.act_window'
        }



    @api.multi
    def create_meters_button(self):
        categs = self.env['service.meter.category']
        for equi in self:
            for template in equi.type_id.template_meter_ids:
                categs |= template.meter_categ_id
            for categ in categs:
                equi.meter_ids.create({'equipment_id': equi.id,
                                       'meter_categ_id': categ.id,
                                       'uom_id': categ.uom_id.id})

    @api.multi
    def update_meter_status(self):
        self._compute_readings_status()

    # o fi ok sa elimin echipmanetul din contract 
    @api.multi
    def remove_from_agreement_button(self):
        self.ensure_one()
        if self.agreement_id.state == 'draft':
            lines = self.env['service.agreement.line'].search(
                [('agreement_id', '=', self.agreement_id.id), ('equipment_id', '=', self.id)])
            lines.unlink()
            if not self.agreement_id.agreement_line:
                self.agreement_id.unlink()
        else:
            raise Warning(_('The agreement %s is in state %s') % (self.agreement_id.name, self.agreement_id.state))


class service_equipment_category(models.Model):
    _name = 'service.equipment.category'
    _description = "Service Equipment Category"
    name = fields.Char(string='Category', translate=True)



class service_equipment_type(models.Model):
    _name = 'service.equipment.type'
    _description = "Service Equipment Type"
    name = fields.Char(string='Type', translate=True)
    categ_id = fields.Many2one('service.equipment.category', string="Category")

    template_meter_ids = fields.One2many('service.template.meter', 'type_id')


# este utilizat pentru generare de pozitii noi in contract si pentru adugare contori noi
class service_template_meter(models.Model):
    _name = 'service.template.meter'
    _description = "Service Template Meter"

    type_id = fields.Many2one('service.equipment.type', string="Type")
    product_id = fields.Many2one('product.product', string='Service', ondelete='set null',  domain=[('type', '=', 'service')])
    meter_categ_id = fields.Many2one('service.meter.category', string="Meter category")
    bill_uom_id = fields.Many2one('product.uom', string='Billing Unit of Measure')
    currency_id = fields.Many2one('res.currency', string="Currency", required=True,
                                  domain=[('name', 'in', ['RON', 'EUR'])])

    @api.onchange('meter_categ_id')
    def onchange_meter_categ_id(self):
        self.bill_uom_id = self.meter_categ_id.bill_uom_id

