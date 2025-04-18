# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields, ModelView
from trytond.pool import Pool
from trytond.wizard import Button, StateTransition, StateView, Wizard
from trytond.transaction import Transaction


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

    def _update_domain(self):
        return [
            ['OR',
                ('shipment', 'ilike', 'stock.shipment.in,%'),
                ('shipment', 'ilike', 'stock.shipment.out,%'),
                ('shipment', 'ilike', 'stock.shipment.in.return,%'),
                ('shipment', 'ilike', 'stock.shipment.out.return,%'),
                ['OR',
                    ('shipment', 'ilike', 'stock.shipment.internal,%'),
                    ('shipment_price_list', '!=', None),
                    ],
                ],
            ('state', '=', 'done'),
            ('company.intrastat', '=', True),
            ]

    def transition_update(self):
        pool = Pool()
        Move = pool.get('stock.move')

        start_date = self.start.period.start_date
        end_date = self.start.period.end_date
        company = Transaction().context.get('company')
        domain = self._update_domain()
        domain.extend([
                ('effective_date', '>=', start_date),
                ('effective_date', '<=', end_date),
                ('company', '=', company),
                ])
        moves = Move.search(domain)
        Move.update_intrastat_declaration(moves)
        return 'end'
