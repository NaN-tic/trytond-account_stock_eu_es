# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta


class Company(metaclass=PoolMeta):
    __name__ = 'company.company'

    intrastat = fields.Boolean("Intrastat")

    @staticmethod
    def default_intrastat():
        return True
