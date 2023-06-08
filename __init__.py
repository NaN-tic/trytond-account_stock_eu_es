# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import country, invoice, purchase, sale, stock

__all__ = ['register']


def register():
    Pool.register(
        country.Country,
        stock.Move,
        stock.ShipmentIn,
        stock.ShipmentOut,
        stock.ShipmentInReturn,
        stock.ShipmentOutReturn,
        stock.ShipmentInternal,
        purchase.PurchaseLine,
        sale.SaleLine,
        stock.IntrastatUpdateStart,
        module='account_stock_eu_es', type_='model')
    Pool.register(
        invoice.Invoice,
        invoice.InvoiceLine,
        module='account_stock_eu_es', type_='model',
        depends=['account_invoice_stock'])
    Pool.register(
        stock.IntrastatUpdate,
        module='account_stock_eu_es', type_='wizard')
