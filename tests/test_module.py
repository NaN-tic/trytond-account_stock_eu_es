# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class AccountStockEuTestCase(ModuleTestCase):
    "Test Account Stock Eu module"
    module = 'account_stock_eu_es'
    extras = ['carrier', 'incoterm', 'sale_shipment_cost']

    @with_transaction()
    def test_move_list_shipment_has_invoice_lines(self):
        'Stock move list shipment view includes invoice_lines'
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Move = pool.get('stock.move')

        view_id = ModelData.get_id('stock', 'move_view_list_shipment')
        view = Move.fields_view_get(view_id=view_id, view_type='tree')
        arch = view['arch']
        self.assertIn('name="invoice_lines"', arch)
        self.assertIn('tree_invisible="1"', arch)


del ModuleTestCase
