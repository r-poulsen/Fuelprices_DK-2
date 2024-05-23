"""Scrapes fuel prices from different Danish fuel companies."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
import re
import shutil
import subprocess
import json
from typing import List
from bs4 import BeautifulSoup as BS
import requests
import pytz

from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from urllib3.util import ssl_

import ssl

# from requests.adapters import HTTPAdapter
# from urllib3.poolmanager import PoolManager
# from urllib3.util import ssl_

# from urllib3.util.ssl_ import create_urllib3_context
import urllib3.util.ssl_
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

from .const import (
    PATH,
)

DK_TZ = pytz.timezone("Europe/Copenhagen")

_LOGGER: logging.Logger = logging.getLogger(__package__)
_LOGGER = logging.getLogger(__name__)

DEFAULT_PRICE_TYPE = "pump"
DIESEL = "diesel"
DIESEL_PLUS = "diesel+"
CHARGE = "lader"
QUICKCHARGE = "lynlader"
OCTANE_95 = "oktan 95"
OCTANE_95_PLUS = "oktan 95+"
OCTANE_100 = "oktan 100"


class FuelPrices:
    """Class to manage fuel prices from different companies."""

    # All the supported companies
    company_keys: List[str] = [
        'circlek',
        'f24',
        'goon',
        'ingo',
        'oil',
        'ok',
        'q8',
        'shell',
        'unox'
    ]

    _companies: dict[str, FuelCompany]

    def __init__(self):
        self._companies = {}

    def load_companies(self, subscribe_companies: List[str], subscribe_products: List[str]):
        """Load fuel companies and their products"""

        if not subscribe_companies:
            subscribe_companies = self.company_keys

        for k in subscribe_companies:
            c = FuelCompany.factory(k, subscribe_products)
            if c is not None:
                self._companies[k] = c

    @property
    def companies(self) -> dict[str, FuelCompany]:
        """
        Returns a dictionary of fuel companies.

        The dictionary contains fuel company names as keys and FuelCompany objects as values.

        Returns:
            dict[str, FuelCompany]: A dictionary of fuel companies.
        """
        return self._companies

    def refresh(self):
        """
        Refreshes the prices for all companies.

        This method iterates through all the companies and calls the `refresh_prices` method for
        each company. If a `ReadTimeout` or `ConnectTimeout` exception occurs during the refresh
        process, a warning message is logged.

        :return: None
        """
        for _, company in self.companies.items():
            try:
                company.refresh_prices()
            except requests.exceptions.ReadTimeout:
                logging.warning(
                    "Read timeout when refreshing prices from %s", company.name)
            except requests.exceptions.ConnectTimeout:
                logging.warning(
                    "Connect timeout when refreshing prices from %s", company.name)
            except requests.exceptions.HTTPError as e:
                logging.warning(
                    "HTTP error when refreshing prices from %s: %s", company.name, e)


class TlsAdapter(HTTPAdapter):

    def __init__(self, ssl_options=0, **kwargs):
        self.ssl_options = ssl_options
        super(TlsAdapter, self).__init__(**kwargs)

    def init_poolmanager(self, *pool_args, **pool_kwargs):
        ctx = ssl_.create_urllib3_context(
            ciphers='AES128-GCM-SHA256:ECDHE-RSA-AES128-SHA256:AES256-SHA', cert_reqs=ssl.CERT_REQUIRED, options=self.ssl_options)
        self.poolmanager = PoolManager(
            *pool_args,
            ssl_context=ctx,
            **pool_kwargs
        )


class FuelCompany:
    """
    Represents a fuel company.

    Attributes:
        _name (str): The name of the fuel company.
        _url (str): The URL of the fuel company's website.
        _products (dict[str, dict]): A dictionary of products offered by the fuel company.
        _key (str): The key representing the fuel company.
    """

    _name: str | None = None
    _url: str | None = None
    _products: dict[str, dict]
    _timeout = 5
    # _key: str | None = None

    _price_type: str = DEFAULT_PRICE_TYPE

    """ 
    The keys of the products that we subscribe to, e.g. "oktan 95", "oktan 100", "diesel", "diesel+"
    """

    def __init__(
            self, subscribe_products: List[str] = None
    ):

        self._session = requests.Session()

        self._session.headers.update({
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            + "AppleWebKit/537.36 (KHTML, like Gecko) "
            + "Chrome/80.0.3987.149 Safari/537.36"
        })

        # if subscribe_products is supplied, remove all products from _products that
        # are not in subscribe_products
        if subscribe_products is not None:
            self._products = {
                k: v for k, v in self._products.items() if k in subscribe_products
            }

        # Also, make a simpler, reverse look index of the products
        self.products_name_key_idx = {
            v['name']: k for k, v in self._products.items()
        }

    @classmethod
    def factory(cls, company_key: str, subscribe_products: List[str]) -> FuelCompany | None:
        """
        Factory method to create an instance of a FuelCompany subclass based on the company_key.

        Args:
            company_key (str): The key representing the fuel company
            subscribe_products ([str]): The products that we wish to subscribe to from this company

        Returns:
            FuelCompany | None: FuelCompany subclass instance if company_key is valid or None
        """
        class_name = __class__.__name__+company_key.capitalize()

        if class_name in globals():
            fuel_company = globals()[class_name](subscribe_products)
            return fuel_company

        _LOGGER.warning("Unknown company key: %s", company_key)
        return None

    @property
    def name(self):
        """
        Returns the company name.
        """
        return self._name

    @property
    def products(self):
        """
        Returns the list of products available.
        """
        return self._products

    @property
    def url(self):
        """
        Returns the main URL for price retrieval.
        """
        return self._url

    @property
    def price_type(self):
        """
        Returns the price type of the fuel.
        """
        return self._price_type

    def refresh_prices(self):
        """
        Refreshes the prices from the fuel company's website.
        """
        _LOGGER.warning("Refreshing prices from %s unsupported", self.name)

    def _get_website(self, url: str = None):
        if url is None:
            url = self._url
        r = self._session.get(url, timeout=self._timeout)
        r.raise_for_status()
        return r

    def _get_html_soup(self, r, parser="html.parser"):
        if r.text:
            return BS(r.text, parser)
        return None

    def _clean_product_name(self, product_name):
        product_name = product_name.replace("Beskrivelse: ", "")
        product_name = product_name.strip()
        if product_name[-1] == ".":
            product_name = product_name[:-1]

        return product_name

    def _clean_price(self, price):
        price = str(price)  # Typecast to String
        # Remove 'Pris inkl. moms: '
        price = price.replace("Pris inkl. moms: ", "")
        price = price.replace(" kr.", "")  # Remove ' kr.'
        price = price.replace(" kr/kWh", "")  # Remove '.'
        price = price.replace(",", ".")  # Replace ',' with '.'
        price = price.strip()  # Remove leading or trailing whitespaces
        # Return the price with 2 decimals
        return f"{float(price):.2f}"

    def _set_price(self, product_key, price_string):
        self._products[product_key]["price"] = float(
            self._clean_price(price_string))
        dt = datetime.now(DK_TZ)
        self._products[product_key]["last_update"] = dt.strftime(
            "%d/%m/%Y, %H:%M:%S")

    def _get_data_from_table(self, product_col, price_col):
        # Use found_price to ensure that we only use the first price found for each product
        found_price = []

        r = self._get_website()
        html = self._get_html_soup(r)
        rows = html.find_all("tr")

        for row in rows:
            cells = row.findAll("td")
            if cells:
                product_name = self._clean_product_name(
                    cells[product_col].text)

                if (
                    product_name not in found_price
                    and product_name in self.products_name_key_idx.keys()
                ):
                    self._set_price(
                        self.products_name_key_idx[product_name], cells[price_col].text
                    )
                    found_price.append(product_name)

    def _download_file(self, url, filename, path):
        r = self._session.get(url, stream=True, timeout=self._timeout)
        r.raise_for_status()
        with open(path + filename, "wb") as file:
            for block in r.iter_content(chunk_size=1024):
                if block:
                    file.write(block)


class FuelCompanyOk(FuelCompany):
    """
    Represents the OK fuel company.

    Attributes:
        _name (str): The name of the fuel company
        _url (str): The URL to fetch daily prices from
        _products (dict[str, dict]): A dict containing the products offered by the fuel company

    Methods:
        refresh_prices: Parses the OK website to extract fuel prices for the given products
    """

    _name: str = "OK"
    _url: str = "https://www.ok.dk/offentlig/produkter/braendstof/priser/vejledende-standerpriser"
    _products: dict[str, dict] = {
        OCTANE_95: {
            "name": "Blyfri 95"
        },
        OCTANE_100: {
            "name": "Oktan 100"
        },
        DIESEL: {
            "name": "Diesel"
        }
    }

    def refresh_prices(self):
        """
        Parses the OK website to extract fuel prices for the given products.

        Args:
            url (str): The URL of the OK website.
            products (dict): A dictionary containing the products to extract prices for.

        Returns:
            dict: A dictionary containing the updated products with prices.
        """

        r = self._get_website()
        html = self._get_html_soup(r)

        rows = html.find_all("div", {"role": "row"})

        for row in rows:
            cells = row.find_all("div", {"role": "gridcell"})
            if cells:
                product_name = self._clean_product_name(cells[0].text)
                if product_name in self.products_name_key_idx.keys():
                    self._set_price(
                        self.products_name_key_idx[product_name], cells[1].text)


class FuelCompanyShell(FuelCompany):
    """
    Represents the Shell fuel company.

    Attributes:
        _name (str): The name of the fuel company.
        _url (str): The URL to fetch daily prices from.
        _products (dict): A dictionary containing the products offered by the fuel company.
    """

    _name: str = "Shell"
    _url: str = "https://shellservice.dk/wp-json/shell-wp/v2/daily-prices"

    _products = {
        OCTANE_95: {"name": "Shell FuelSave 95 oktan"},
        OCTANE_100: {"name": "Shell V-Power 100 oktan"},
        DIESEL: {"name": "Shell FuelSave Diesel"},
        DIESEL_PLUS: {"name": "Shell V-Power Diesel"},
        QUICKCHARGE: {"name": "El/kWh", "type": "electricity"}
    }

    def __init__(self, subscribe_products: List[str] = None):
        super().__init__(subscribe_products)
        adp = TlsAdapter(ssl.OP_NO_TLSv1_1 | ssl.OP_NO_TLSv1_2)
        self._session.mount("https://", adp)  # adp instead of adapter

    def refresh_prices(self):
        r = self._get_website()

        try:
            json_data = r.json()

        except requests.exceptions.JSONDecodeError as e:
            _LOGGER.error("Error parsing JSON from Shell: %s", e)
            raise e

        for product in json_data["results"]["products"]:
            if product["name"] in self.products_name_key_idx.keys():
                self._set_price(
                    self.products_name_key_idx[product["name"]],
                    product["price_incl_vat"]
                )


class FuelCompanyCirclek(FuelCompany):
    """
    Represents the Circle K fuel company.

    Attributes:
        _name (str): The name of the fuel company.
        _url (str): The URL to fetch daily prices from.
        _products (dict): A dictionary containing the products offered by the fuel company.
    """
    _name: str = "Circle K"
    _url: str = "https://www.circlek.dk/priser"

    _products = {
        OCTANE_95: {"name": "miles95"},
        OCTANE_95_PLUS: {"name": "miles+95"},
        DIESEL:  {"name": "miles Diesel"},
        DIESEL_PLUS: {"name": "miles+ Diesel"},
        QUICKCHARGE: {"name": "El Lynlader", "type": "electricity"}
    }

    def refresh_prices(self):
        self._get_data_from_table(1, 2)


class FuelCompanyF24(FuelCompany):
    """
    Represents the F24 fuel company.

    Attributes:
        _name (str): The name of the fuel company.
        _url (str): The URL to fetch electricity prices from.
        _json_url (str): JSON to fetch daily fuel prices from.
        _products (dict): A dictionary containing the products offered by the fuel company.
    """
    _name: str = "F24"
    _json_url: str = "https://www.f24.dk/-/api/PriceViewProduct/GetPriceViewProducts"
    _url: str = "https://www.f24.dk/priser/"

    _products = {
        OCTANE_95: {"name": "GoEasy 95 E10", "ProductCode": 22253},
        OCTANE_95_PLUS: {"name": "GoEasy 95 Extra E5", "ProductCode": 22603},
        DIESEL:  {"name": "GoEasy Diesel", "ProductCode": 24453},
        DIESEL_PLUS: {"name": "GoEasy Diesel Extra", "ProductCode": 24338},
        CHARGE: {"name": "Hurtiglader", "type": "electricity"}
    }

    def refresh_fuel_prices(self):
        # F24 and Q8 returns JSON and expects us to ask with a payload in JSON
        headers = {"Content-Type": "application/json"}
        # Let us prepare a nice payload
        now = datetime.now()
        payload = {}
        # F24/Q8 wish to have a "FromDate", we use today - 31 days as timestamp
        payload["FromDate"] = int((now - timedelta(days=31)).timestamp())
        # Today as timestamp
        payload["ToDate"] = int(now.timestamp())
        # Lets cook up some wanted fueltypes with a empty list
        payload["FuelsIdList"] = []
        # We can control the order of the returned data with a Index
        index = 0
        # Loop through the products, excluding the electric products without a product code
        for product_key, product_dict in self._products.items():
            if "ProductCode" in product_dict:
                product_dict["Index"] = index
                payload["FuelsIdList"].append(product_dict)
                index += 1

        # Send our payload and headers to the URL as a POST
        r = self._session.post(
            self._json_url, headers=headers,
            data=str(payload), timeout=self._timeout
        )
        r.raise_for_status()

        for product_key, product_dict in self._products.items():
            if "ProductCode" in product_dict:
                # Extract the data of the product at the given Index from the dictionary
                # Remember we told the server in which order we wanted the data
                json_product = r.json()[
                    "Products"][product_dict["Index"]]
                # Get only the name and the price of the product

                self._set_price(
                    product_key, json_product["PriceInclVATInclTax"])

    def refresh_electric_prices(self):
        # This is a bit of a hack, but it works
        prices = self._get_html_soup(
            self._get_website()
        ).find_all("tr")[3].find_all("td")[1:]

        if len(prices) == 2:
            if QUICKCHARGE in self.products_name_key_idx.values():
                self._set_price(QUICKCHARGE, prices[0].text)
            prices.pop(0)

        if CHARGE in self.products_name_key_idx.values():
            self._set_price(CHARGE, prices[0].text)

    def refresh_prices(self):
        self.refresh_fuel_prices()

        if (
            QUICKCHARGE in self.products_name_key_idx.values()
            or CHARGE in self.products_name_key_idx.values()
        ):
            self.refresh_electric_prices()


class FuelCompanyQ8(FuelCompanyF24):
    """
    Represents the Q8 fuel company.

    Attributes:
        _name (str): The name of the fuel company.
        _url (str): The URL to fetch electricity prices from.
        _json_url (str): JSON to fetch daily fuel prices from.
        _products (dict): A dictionary containing the products offered by the fuel company.
    """
    _name: str = "Q8"
    _json_url: str = "https://www.q8.dk/-/api/PriceViewProduct/GetPriceViewProducts"
    _url: str = "https://www.q8.dk/priser/"

    _products = {
        OCTANE_95: {"name": "GoEasy 95 E10", "ProductCode": 22251},
        OCTANE_95_PLUS: {"name": "GoEasy 95 Extra E5", "ProductCode": 22601},
        DIESEL:  {"name": "GoEasy Diesel", "ProductCode": 24451},
        DIESEL_PLUS: {"name": "GoEasy Diesel Extra", "ProductCode": 24337},
        CHARGE: {"name": "Hurtiglader", "type": "electricity"},
        QUICKCHARGE: {"name": "Lynlader", "type": "electricity"}
    }


class FuelCompanyIngo(FuelCompany):
    """
    Represents the Ingo fuel company.

    Attributes:
        _name (str): The name of the fuel company.
        _url (str): The URL to fetch daily prices from.
        _products (dict): A dictionary containing the products offered by the fuel company.
    """
    _name: str = "Ingo"
    _url: str = "https://www.ingo.dk/br%C3%A6ndstofpriser/aktuelle-br%C3%A6ndstofpriser"

    _products = {
        OCTANE_95: {"name": "Benzin 95"},
        OCTANE_95_PLUS: {"name": "UPGRADE 95"},
        DIESEL:  {"name": "Diesel"},
    }

    def refresh_prices(self):
        self._get_data_from_table(1, 2)


class FuelCompanyOil(FuelCompany):
    """
    Represents the OIL! fuel company.

    Attributes:
        _name (str): The name of the fuel company.
        _url (str): The URL to fetch daily prices from.
        _products (dict): A dictionary containing the products offered by the fuel company.
    """
    _name: str = "OIL!"
    _url: str = "https://www.oil-tankstationer.dk/de-gaeldende-braendstofpriser/"

    _products = {
        OCTANE_95: {"name": "95 E10"},
        OCTANE_95_PLUS: {"name": "PREMIUM 98"},
        DIESEL:  {"name": "Diesel"},
    }

    def refresh_prices(self):
        r = self._get_website()
        html = self._get_html_soup(r)
        rows = html.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if cells:
                product_name = self._clean_product_name(cells[0].text)
                if product_name in self.products_name_key_idx.keys():
                    self._set_price(
                        self.products_name_key_idx[product_name], cells[2].text)


class FuelCompanyGoon(FuelCompany):
    """
    Represents the Go' On fuel company.

    Uses ssocr to OCR the prices from an image.

    Attributes:
        _name (str): The name of the fuel company.
        _url (str): The URL to fetch daily prices from.
        _products (dict): A dictionary containing the products offered by the fuel company.
    """
    _name: str = "Go' on"
    _url: str = "https://goon.nu/priser/#Aktuellelistepriser"

    _products = {
        OCTANE_95: {"name": "Blyfri 95", "ocr_crop": ["58", "232", "134", "46"]},
        "diesel":  {"name": "Transportdiesel", "ocr_crop": ["58", "289", "134", "46"]},
    }

    def refresh_prices(self):
        # Test if SSOCR, Seven Segments OCR, is present
        ssocr_bin = shutil.which("ssocr")
        if not ssocr_bin:
            _LOGGER.error(
                "Ssocr not present - OCR of prices from Go'On not possible. " +
                "Will fetch 'listepriser'"
            )
            self._goon_list_prices()
        else:
            self._goon_ocr()

    # GO'ON - No SSOCR present, get the "listprices"
    def _goon_list_prices(self):
        # Fetch the prices using the table-scraper function
        self._get_data_from_table(0, 7)
        # Since we are scraping "Listepriser" add 'priceType' : 'list' to the products
        # This is merely to send a message back to the API.
        self._price_type = "list"

    # GO'ON SSOCR present

    def _goon_ocr(self):
        # Filename for the image with the prices
        prices_file = "goon_prices.png"

        # Fetch the website with the prices
        r = self._get_website()
        html = self._get_html_soup(r)

        # Extract the url for the image with the prices and download the file
        pricelist_url = html.find("img", class_="lazyload")["data-src"]
        _LOGGER.debug("Latest Go'On price images is this: %s", pricelist_url)
        self._download_file(pricelist_url, prices_file, PATH)

        # # Loop through the products
        for product_key, product_dict in self._products.items():
            # Create a command for the SSOCR
            ocr_cmd = (
                ["ssocr"]
                + ["-d5"]
                + ["-t20"]
                + ["make_mono", "invert", "-D"]
                + ["crop"]
                + product_dict["ocr_crop"]
                + [PATH + prices_file]
            )
            # Perform OCR on the cropped image
            with subprocess.Popen(
                ocr_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            ) as ocr:
                out = ocr.communicate()
                if out[0] != b"":
                    _LOGGER.debug(
                        "%s: %s", product_dict["name"], out[0].strip().decode("utf-8"))
                    self._set_price(
                        product_key, out[0].strip().decode("utf-8"))


class FuelCompanyUnox(FuelCompany):
    """
    Represents the UNO-X fuel company.

    Attributes:
        _name (str): The name of the fuel company.
        _url (str): The URL to display to end users.
        _js_url (str): The JSON URL to fetch daily prices from.
        _products (dict): A dictionary containing the products offered by the fuel company.
    """
    _name: str = "Uno-X"
    _url: str = "https://bilist.unoxmobility.dk/braendstofpriser"
    _js_url: str = "https://bilist.unoxmobility.dk/umbraco/surface/PriceListData/PriceList"

    _products = {
        OCTANE_95: {"name": "Blyfri 95 E10"},
        OCTANE_95_PLUS: {"name": "Blyfri 98 E5"},
        OCTANE_100: {"name": "Blyfri 100 E5"},
        DIESEL:  {"name": "Diesel"},
    }

    def refresh_prices(self):
        # Uno-X returns not quite JSON.
        # {"Date":"\/Date(1700407231204)\/","DateFormatted":"19. nov. 2023",
        # "DateUnixEpoc":1700407231,"Product":"Blyfri 100 E5","ListPriceExclVat":13.431,
        # "ListPriceInclVat":16.79,"PumpPrice":14.78}
        r = self._get_website(url=self._js_url)
        # iterate over each matching pattern
        for match in re.finditer(r"({\"Date[^}]*})", r.text):
            json_string = match.group(0)
            # parse the JSON string
            json_data = json.loads(json_string)
            # check if the product is in our list
            if json_data["Product"] in self.products_name_key_idx.keys():

                if (
                    "DateUnixEpoc" not in self._products[
                        self.products_name_key_idx[json_data["Product"]]
                    ] or
                        self._products[
                            self.products_name_key_idx[json_data["Product"]]
                    ]["DateUnixEpoc"] <= json_data['DateUnixEpoc']
                ):

                    # set the price
                    self._set_price(
                        self.products_name_key_idx[json_data["Product"]],
                        json_data["PumpPrice"]
                    )

                    self._products[
                        self.products_name_key_idx[json_data["Product"]]
                    ]["DateUnixEpoc"] = json_data['DateUnixEpoc']
