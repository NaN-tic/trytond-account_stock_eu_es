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
        InvoiceLine = pool.get('account.invoice.line')

        lines = [l for i in invoices for l in i.lines]
        InvoiceLine.update_intrastat_move_line_amount(lines)


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @classmethod
    def update_intrastat_move_line_amount(cls, lines):
        pool = Pool()
        Move = pool.get('stock.move')

        moves = []
        for line in lines:
            # Ensure that cache only take this 'line' an not 1.000
            # registers. Beacsue in some cases the line may don't have and
            # ivoice assocaited yet and it's needed for the company_amount
            # field calculation.
            line = cls(line)
            if (not line.invoice
                    or line.invoice.state not in ('posted', 'paid')):
                continue
            invoice_date = (line.invoice.accounting_date
                or line.invoice.invoice_date)
            invoice_date = invoice_date.replace(day=1)
            for move in line.stock_moves:
                if not move.intrastat_type or not move.intrastat_incoterm:
                    continue
                move_date = move.effective_date or move.planned_date
                move_date = move_date.replace(day=1)
                if move_date != invoice_date:
                    continue
                if move.intrastat_declaration.state != 'opened':
                    continue
                amount = (line.company_amount
                    if hasattr(line, 'company_amount') else line.amount)

                # TODO: control correctly the possiblity to have multiple
                # invoice lines associated the same move line.

                # In this cases it will be a refund for the advanced payment.
                if amount < 0:
                    move.intrastat_value += line.company_amount
                # In this cases will a update cost.
                elif line.quantity == move.quantity:
                    move.intrastat_value = line.company_amount
                moves.append(move)
        if moves:
            Move.save(moves)
