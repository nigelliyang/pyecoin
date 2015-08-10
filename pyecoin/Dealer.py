import hashlib
import hmac
import random
import requests
import logging
import collections
import json
import time
import logging
from shared_conf import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)20s - %(name)20s - %(levelname)20s - %(message)20s')
ch.setFormatter(formatter)
logger.addHandler(ch)


class DealerConst():
	NONCE = "nonce"
	KEY = "key"
	SIGNATURE = "signature"
	COIN = "coin"
	AMOUNT_ORIGINAL = "amount_original"
	AMOUNT_OUTSTANDING = "amount_outstanding"
	PRICE = "price"
	TYPE = "type"
	ID = "id"
	DAYTIME = "daytime"
	STATUS = "status"
	VERSION = "version"
	AMOUNT = "amount"
	SINCE = "since"

class Dealer():
	"""
	Class used to do transactions on particular markets. By now 2 markets have been supported, namely btctrade.com and jubi.com
	usage example:
	d = Dealer(market = "btctrade", coin = "ltc", public_key = "{your publib key}", secret_key = "{you secret key}", logging = True)
	d.get_balance()
	d.buy(price = 1.0, amount = 1.0)
	"""

	def __init__(self, market = "btctrade", coin = "ltc", public_key = None, secret_key = None, logging = False):
		if logging:
			logger.info('initilize. market: %s, coin type: %s', market, coin)
		if market not in ("btctrade", "jubi"):
			raise Exception("Unknown market. Report to xfanzone@gmail.com to add support.")
		self._market = market
		if self._market == "btctrade":
			self._base_url = "http://api.btctrade.com/api"
		if self._market == "jubi":
			self._base_url = "http://www.jubi.com/api/v1"
		self._coin = coin
		self._public_key = public_key
		if secret_key is not None:
			self._hash_key = hashlib.md5(secret_key).hexdigest()
		else:
			self._hash_key = None
		self._logging = logging

	def get_balance(self):
		"""
		get current balance
		"""
		self._url = self._get_request_url('balance')
		self._get_basic_payload()
		self._post_signatured_payload()
		resp = self.resp.json()
		if self._speed_issue(resp):
			time.sleep(2)
			return self.get_balance()
		for k, v in resp.iteritems():
			if '_lock' in k:
				resp[k.replace('_lock', '_reserved')] = resp[k]
				del resp[k]
		return resp

	def get_orders(self, order_type = "open", since = None):
		"""
		get orders issued by yourself
		"""
		self._url = self._get_request_url('orders')
		self._get_basic_payload()
		self._set_coin()
		if self._market == "btctrade" and since is not None:
			if self._logging:
				logger.warning("btctrade does not support `since' keyword, omitting")
			since = None
		if since is not None:
			self._set_get_order_since(since)
		self._set_get_orders_type(order_type)
		self._post_signatured_payload()
		resp = self.resp.json()
		if self._speed_issue(resp):
			time.sleep(2)
			return self.get_orders()
		return resp

	def fetch_order(self, orderId):
		"""
		fetch order information by order id
		"""
		self._url = self._get_request_url('fetch_order')
		self._get_basic_payload()
		self._set_orderId(orderId)
		self._post_signatured_payload()
		resp = self.resp.json()
		if self._speed_issue(resp):
			time.sleep(2)
			return self.fetch_order(orderId)
		return resp

	def cancel_order(self, orderId):
		"""
		cancel order by order id
		"""
		self._url = self._get_request_url('cancel_order')
		self._get_basic_payload()
		self._set_orderId(orderId)
		self._post_signatured_payload()
		resp = self.resp.json()
		if self._logging:
			logger.debug("cancel order: %s", resp.__str__())
		if self._speed_issue(resp):
			time.sleep(2)
			return self.cancel_order(orderId)
		return resp

	def buy(self, price, amount):
		"""
		buy `amount' coin at `price'
		"""
		self._url = self._get_request_url('buy')
		self._get_basic_payload()
		self._set_coin()
		self._set_amount(amount)
		self._set_price(price)
		if self._market == "jubi":
			self._set_trade_type("buy")
		self._post_signatured_payload()
		resp = self.resp.json()
		if self._speed_issue(resp):
			time.sleep(2)
			return self.buy(price, amount)
		return resp

	def sell(self, price, amount):
		"""
		sell `amount' coin at `price'
		"""
		self._url = self._get_request_url('sell')
		self._get_basic_payload()
		self._set_coin()
		self._set_amount(amount)
		self._set_price(price)
		if self._market == "jubi":
			self._set_trade_type("sell")
		self._post_signatured_payload()
		resp = self.resp.json()
		if self._speed_issue(resp):
			time.sleep(2)
			return self.sell(price, amount)
		return resp

	def _generate_signature(self):
		para_dict = self.payload
		str_list = []
		for k, v in para_dict.iteritems():
			str_list.append(str(k) + "=" + str(v))
		str_to_sig = "&".join(str_list)
		sig = hmac.new(self._hash_key, str_to_sig, hashlib.sha256).hexdigest()
		para_dict[DealerConst.SIGNATURE] = sig

	def _generate_nonce(self, length=13):
		"""Generate pseudorandom number."""
		#nonce = ''.join([str(random.randint(0, 9)) for i in range(length)])
		nonce = str(int(round(time.time() * 1000)))
		return nonce

	def _build_http_param(self):
		para_dict = self.payload
		str_list = []
		for k, v in para_dict.iteritems():
			str_list.append(str(k) + "=" + str(v))
		str_to_sig = "&".join(str_list)
		return str_to_sig

	def _get_basic_payload(self):
		if self._public_key is None:
			raise Exception('public key not set')
		self.payload = collections.OrderedDict()
		self.payload[DealerConst.NONCE] = self._generate_nonce()
		if self._market == "btctrade":
			self.payload[DealerConst.VERSION] = 2
		self.payload[DealerConst.KEY] = self._public_key

	def _post_signatured_payload(self):
		self._generate_signature()
		self._post_data()

	def _post_data(self):
		http_param = self._build_http_param()
		if self.logging:
			logger.info("request for %s with data: %s", self._url, http_param)
		self.resp = requests.post(self._url, http_param, headers = headers)

	def _set_orderId(self, orderId):
		self.payload[DealerConst.ID] = orderId

	def _set_coin(self):
		self.payload[DealerConst.COIN] = "ltc"

	def _set_amount(self, amount):
		self.payload[DealerConst.AMOUNT] = amount

	def _set_price(self, price):
		self.payload[DealerConst.PRICE] = price

	def _set_get_orders_type(self, order_type):
		self.payload[DealerConst.TYPE] = order_type

	def _set_get_order_since(self, since):
		self.payload[DealerConst.SINCE] = since

	def _set_trade_type(self, trade_type):
		self.payload[DealerConst.TYPE] = trade_type

	def is_buy_done(self, orderId):
		"""
		return a float between 0 and 1, indicating the percentage that is done of the order 
		"""
		resp = self.fetch_order(orderId)
		amount_original = float(resp[DealerConst.AMOUNT_ORIGINAL])
		amount_outstanding = float(resp[DealerConst.AMOUNT_OUTSTANDING])
		return 1 - amount_outstanding / amount_original

	def is_sell_done(self, orderId):
		"""
		return a float between 0 and 1, indicating the percentage that is done of the order 
		"""
		resp = self.fetch_order(orderId)
		if self._speed_issue(resp):
			return self.is_sell_done(orderId)
		amount_original = float(resp[DealerConst.AMOUNT_ORIGINAL])
		amount_outstanding = float(resp[DealerConst.AMOUNT_OUTSTANDING])
		return 1 - amount_outstanding / amount_original

	def _speed_issue(self, resp):
		if type(resp) == dict and 'message' in resp.keys() and 'result' in resp.keys() and resp['result'] == False and "S_U_001" in resp['message']:
			return True
		return False

	def _get_request_url(self, request_type):
		if self._market == "btctrade":
			url = "{0}/{1}?coin={2}".format(self._base_url, btctrade_api[request_type], self._coin)
		elif self._market == "jubi":
			url = "{0}/{1}/?coin={2}".format(self._base_url, jubi_api[request_type], self._coin)
		return url

