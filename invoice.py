# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.model import ModelView, Workflow


class Invoice(metaclass=PoolMeta):
    __name__ = 'stock.move'

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, invoices):
        pool = Pool()
        Move = pool.get('stock.move')

        moves = []
        for invoice in invoices:
            #invoice_date = invoice.accounting_date or invoice.invoice_date
            #invoice_date = invoice_date.replace(day=1)
            for line in invoice.lines:
                for move in line.stock_moves:
                    if not move.intrastat_type or not move.intrastat_incoterm:
                        continue
                    #move_date = move.effective_date or move.planned_date
                    #move_date = move_date.replace(day=1)
                    #if move_date != invoice_date:
                    #    continue
                    if move.intrastata_declaration.state != 'opened':
                        continue
                    # TODO: By the moment it's a depends to account_invoice_company_currency. But may be will be better to be an extradepends ¿?
                    if line.company_amount < 0:
                        move.intrastat_value += line.company_amount
                    elif line.quantity == move.quantity:
                        move.intrastat_value = line.company_amount
                    moves.append(move)
        if moves:
            Move.save(moves)
