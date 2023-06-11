# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields, ModelView
from trytond.pool import Pool
from trytond.wizard import Button, StateTransition, StateView, Wizard


class IntrastatUpdateStart(ModelView):
    "Intrastat Update Start"
    __name__ = 'account.stock.eu.intrastat.update.start'

    period = fields.Many2One('account.period', 'Period', required=True,
        domain=[
            ('type', '=', 'standard'),
            ])


class IntrastatUpdate(Wizard):
    "Intrastat Update"
    __name__ = 'account.stock.eu.intrastat.update'
    start = StateView(
        'account.stock.eu.intrastat.update.start',
        'account_stock_eu_es.intrastat_update_start_view_form', [
            Button("Cancel", 'end', 'tryton-close'),
            Button("Update", 'update', 'tryton-ok'),
            ])
    update = StateTransition()

    def transition_update(self):
        pool = Pool()
        Move = pool.get('stock.move')

        start_date = self.start.period.start_date
        end_date = self.start.period.end_date
        moves = Move.search([
                ['OR',
                    ('shipment', 'ilike', 'stock.shipment.in,%'),
                    ('shipment', 'ilike', 'stock.shipment.out,%'),
                    ('shipment', 'ilike', 'stock.shipment.in.return,%'),
                    ('shipment', 'ilike', 'stock.shipment.out.return,%')],
                ('state', '=', 'done'),
                ('effective_date', '>=', start_date),
                ('effective_date', '<=', end_date),
                ])
        Move.update_intrastat_declaration(moves)
        return 'end'
