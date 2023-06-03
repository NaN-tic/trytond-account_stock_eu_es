# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


class PurchaseLine(metaclass=PoolMeta):
    __name__ = 'purchase.line'

    def get_move(self, move_type):
        move = super().get_move(move_type)
        if not move:
            return
        move.intrastat_incoterm = (self.purchase.incoterm
            if self.purchase and self.purchase.incoterm else None)
        return move
