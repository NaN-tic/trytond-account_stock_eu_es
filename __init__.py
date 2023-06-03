# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import invoice, purchase, sale, stock

__all__ = ['register']


def register():
    Pool.register(
        stock.Move,
        stock.ShipmentIn,
        stock.ShipmentOut,
        purchase.PurchaseLine,
        sale.SaleLine,
        module='account_stock_eu', type_='model')

    Pool.register(
        invoice.Invoice,
        module='account_stock_eu', type_='model',
        depends=['account_invoice_stock'])
