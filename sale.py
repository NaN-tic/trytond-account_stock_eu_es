# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


class SaleLine(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    def get_move(self, move_type):
        move = super().get_move(move_type)
        if not move:
            return
        move.intrastat_incoterm = (self.sale.incoterm
            if self.sale and self.sale.incoterm else None)
        return move
