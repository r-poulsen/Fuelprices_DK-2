#!/bin/env python

import logging
import time
from fuelprices_dk import FuelPrices


DIESEL = "diesel"
DIESEL_PLUS = "diesel+"
CHARGE = "lader"
QUICKCHARGE = "lynlader"
OCTANE_95 = "oktan 95"
OCTANE_95_PLUS = "oktan 95+"
OCTANE_100 = "oktan 100"


test_companies = {
    # 'circlek': [OCTANE_95, OCTANE_95_PLUS, DIESEL, DIESEL_PLUS, QUICKCHARGE],
    # 'f24': [OCTANE_95, OCTANE_95_PLUS, DIESEL, DIESEL_PLUS, CHARGE],
    # 'goon': [OCTANE_95, DIESEL],
    # 'ingo': [OCTANE_95, OCTANE_95_PLUS, DIESEL],
    # 'oil': [OCTANE_95, OCTANE_95_PLUS, DIESEL],
    # 'ok': [OCTANE_95, OCTANE_100, DIESEL],
    # 'q8': [OCTANE_95, OCTANE_95_PLUS, DIESEL, DIESEL_PLUS, CHARGE, QUICKCHARGE],
    # 'shell': [OCTANE_95, OCTANE_100, DIESEL, DIESEL_PLUS, QUICKCHARGE],
    'unox': [OCTANE_95, OCTANE_95_PLUS, OCTANE_100, DIESEL],
}

# test_companies = {
#     'circlek': [OCTANE_95, OCTANE_95_PLUS, DIESEL, DIESEL_PLUS, QUICKCHARGE],
#     'unox': [OCTANE_95, OCTANE_95_PLUS, OCTANE_100, DIESEL],
# }


# logging.basicConfig(level=logging.DEBUG)
_LOGGER: logging.Logger = logging.getLogger(__package__)
_LOGGER = logging.getLogger(__name__)

f = FuelPrices()
f.load_companies(None, None)

f.refresh()
for company, products in test_companies.items():
    for product in products:
        try:
            print(
                f'{f.companies[company].name:10s} {product:12s} ' +
                f'{f.companies[company].products[product]["name"]:23s} ' +
                f'{f.companies[company].products[product]["price"]:6.2f} '
            )

        except KeyError:
            print(
                f'KeyError: {product} or price not found (company: {company})'
            )

    print()
