# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.model import fields


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @property
    @fields.depends('company', 'warehouse', 'shipment_address', 'sale_date')
    def _incoterm_required(self):
        pool = Pool()
        Date = pool.get('ir.date')

        today = Date.today()
        if self.company and self.company.incoterms:
            if (self.warehouse and self.warehouse.address
                    and self.warehouse.address.country
                    and self.warehouse.address.country.in_intrastat(
                        date=self.sale_date or today)
                    and self.shipment_address
                    and self.shipment_address.country
                    and self.shipment_address.country.in_intrastat(
                        date=self.sale_date or today)):
                return (
                    self.warehouse.address.country
                    != self.shipment_address.country)
        return False


class SaleLine(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    def get_move(self, move_type):
        move = super().get_move(move_type)
        if not move:
            return
        move.intrastat_incoterm = (self.sale.incoterm
            if self.sale and self.sale.incoterm else None)
        return move
