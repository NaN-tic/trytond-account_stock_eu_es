# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


class Country(metaclass=PoolMeta):
    __name__ = 'country.country'

    @property
    def is_in_intrastat(self):
        return self.in_intrastat()
