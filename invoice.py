# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.pool import Pool, PoolMeta
from trytond.model import ModelSQL, fields
from trytond.modules.company.model import CompanyValueMixin


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'

    intrastat_discount_product = fields.MultiValue(
        fields.Many2One('product.product', "Intrastat Discount Product",
            help="If setted, when calcaulate the amount of the Intrastata move"
            " it take the discount line if exit from the same invoice."))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'intrastat_discount_product'}:
            return pool.get('account.configuration.intrastat')
        return super().multivalue_model(field)


class ConfigurationIntrastat(ModelSQL, CompanyValueMixin):
    "Account Configuration Intrastat"
    __name__ = 'account.configuration.intrastat'

    intrastat_discount_product = fields.Many2One('product.product',
        "Intrastat Discout Product")


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    def get_invoice_intrastat_discount_per_line(cls, invoices):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        Configuration = pool.get('account.configuration')

        config = Configuration(1)
        discount_product = config.intrastat_discount_product
        # Needs invoices in order from old to new, to ensure apply correctly
        # the amount of each line in the time order.
        invoices = cls.search([
                ('id', 'in', [i.id for i in invoices]),
                ], order=[('invoice_date', 'ASC')])
        if discount_product:
            lines = {}
            for invoice in invoices:
                aux_lines = {}
                discount = Decimal('0.0')
                quantity = 0
                # As normaly the discount line will be negative apply it at
                # the end of the loop.
                invoice_lines = InvoiceLine.search([
                        ('id', 'in', [l.id for l in invoice.lines]),
                        ], order=[('quantity', 'DESC')])
                # TODO: Control lines UoM to calculate the discount per unit
                for line in invoice_lines:
                    if line.product == discount_product:
                        discount += (line.company_amount
                            if hasattr(line, 'company_amount')
                            else line.amount)
                    else:
                        quantity += line.quantity
                        amount = (line.company_amount
                            if hasattr(line, 'company_amount') else line.amount)
                        aux_lines[line] = amount
                if quantity and discount:
                    discount_per_unit = discount / Decimal(
                        str(quantity or '0.0'))
                    for key, value in aux_lines.items():
                        aux_lines[key] += (Decimal(str(key.quantity or '0.0'))
                            * discount_per_unit)
                lines.update(aux_lines)
        else:
            lines = {l: Decimal('0.0') for i in invoices for l in i.lines}
        return lines

    @classmethod
    def _post(cls, invoices):
        pool = Pool()
        Move = pool.get('stock.move')

        # Get all the stock move related with the invoce lines, to update they
        # intrastat_value if it's required.
        lines = [l for i in invoices for l in i.lines]
        moves = [m for l in lines for m in l.stock_moves]
        super()._post(invoices)
        Move.update_intrastat_declaration(moves)

    @classmethod
    def cancel(cls, invoices):
        pool = Pool()
        Move = pool.get('stock.move')

        super().cancel(invoices)
        # Get all the sotck move related with the invoce lines, to remove from
        # the Intrastata report.
        lines = [l for i in invoices for l in i.lines]
        moves = [m for l in lines for m in l.stock_moves
            if m.intrastat_type is not None]
        values = {
            'intrastat_cancelled': True,
            'intrastat_type': None,
            'intrastat_declaration': None,
            }
        Move.write(moves, values)
        moves = Move.browse(moves)
        Move.update_intrastat_declaration(moves)

    @classmethod
    def draft(cls, invoices):
        pool = Pool()
        Move = pool.get('stock.move')

        super().draft(invoices)
        # Get all the sotck move related with the invoce lines, to remove from
        # the Intrastata report.
        lines = [l for i in invoices for l in i.lines]
        moves = [m for l in lines for m in l.stock_moves
            if m.intrastat_cancelled]
        values = {
            'intrastat_cancelled': False,
            }
        Move.write(moves, values)
        moves = Move.browse(moves)
        Move.update_intrastat_declaration(moves)
