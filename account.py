# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


class FiscalYear(metaclass=PoolMeta):
    __name__ = 'account.fiscalyear'

    @staticmethod
    def default_intrastat_extended():
        return True
