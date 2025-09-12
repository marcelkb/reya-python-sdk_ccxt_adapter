# CCXT-style exchange wrapper for Reya (uses ccxt.Exchange machinery for HTTP).
#
# Requirements:
#   pip install ccxt
#
# Design:
# - Uses ccxt's request helpers (publicGetXXX / privatePostXXX).
# - Only uses Reya SDK for private calls
#
# Endpoints mapped from Reya docs:
# "v2/marketDefinitions"
# "v2/market/{symbol}/summary"
# "v2/prices/{symbol}"
# "v2/wallet/{address}/accountBalances"
# "candleHistory/{symbol}/{resolution}"
# "wallet/{address}/positions"
# "/wallet/{wallet_address}/accountBalances"
# "api/trading/wallet/{address}/accounts/balances"
# "api/trading/wallet/{wallet_address}/leverages"
# "/v2/wallet/{address}/accounts"
# "/v2/wallet/{wallet_address}/openOrders"
# "wallet/{address}/perpExecutions"
# "api/trading/poolBalance/{pool_id}"
#
# Notes:
# - This file intentionally keeps parsing minimal and returns raw data in `info` fields.
# - If Reya changes endpoints/names, update the 'api' map and method paths below.

from __future__ import annotations

import asyncio
import json
import math
import time
from datetime import datetime
from decimal import Decimal
from io import UnsupportedOperation
from typing import Optional, Dict, Any, List

from ccxt.base.types import Str, Int, FundingRate, OrderSide, Num, Strings

from ccxt_wrapper.abstract.Reya import ImplicitAPI
from ccxt_wrapper.const import EOrderSide, EOrderStatus, EOrderType
from sdk.open_api import CreateOrderResponse, TimeInForce, CancelOrderResponse, OrderType
from sdk.reya_rest_api import ReyaTradingClient
from sdk.reya_rest_api.config import REYA_DEX_ID
from sdk.reya_rest_api.models import TriggerOrderParameters, LimitOrderParameters

try:
    import ccxt  # type: ignore
except Exception as e:
    raise RuntimeError("ccxt is required. Install with: pip install ccxt") from e


def _now_ms() -> int:
    return int(time.time() * 1000)


def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # no loop exists, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        # already inside an async loop → create a blocking task
        future = asyncio.ensure_future(coro)
        # run_until_complete cannot be called if loop is running,
        # so we have to use nest_asyncio or similar in that case
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(future)
    else:
        return loop.run_until_complete(coro)

class Reya(ccxt.Exchange, ImplicitAPI):
    def describe(self) -> Dict[str, Any]:
        return self.deep_extend(super(Reya, self).describe(), {
            "id": "reya",
            "name": "Reya",
            "countries": ["US"],  # change if needed
            "rateLimit": 1000,
            "version": "v2",
            "has": {
                "fetchMarkets": True,
                "fetchTickers": True,
                "fetchTicker": True,
                "fetchOrderBook": True,
                "fetchOHLCV": True,
                "fetchTrades": True,
                "fetchBalance": True,
                "createOrder": True,
                "cancelOrder": True,
                "fetchOrder": True,
                "fetchOrders": True,
                "fetchOpenOrders": True,
                "fetchMyTrades": True,
                "deposit": True,
                "withdraw": True,
            },
            "urls": {
                "api": {
                    "public": "https://api.reya.xyz",
                    "private": "https://api.reya.xyz",
                },
                "docs": "https://docs.reya.xyz/technical-docs/reya-dex-rest-api-v2",
            },
            "api": {
                "public": {
                    "get": {
                        # markets & public data
                        "v2/marketDefinitions": 1,
                        "v2/market/{symbol}/summary": 1,
                        "v2/prices/{symbol}": 1,
                        "v2/wallet/{address}/accountBalances":1,
                        "candleHistory/{symbol}/{resolution}":1,
                        "wallet/{address}/positions":1,
                        "/wallet/{wallet_address}/accountBalances":1,
                        "api/trading/wallet/{address}/accounts/balances": 1,
                        "api/trading/wallet/{wallet_address}/leverages": 1,
                        "/v2/wallet/{address}/accounts":1,
                        "/v2/wallet/{wallet_address}/openOrders":1,
                        "wallet/{address}/perpExecutions":1,
                        "api/trading/poolBalance/{pool_id}":1
                    },
                },
                "private": {
                    "get": {
                    },
                    "post": {
                    },
                },
            },
            'fees': {
                'swap': {
                    'taker': self.parse_number('0.0004'),
                    'maker': self.parse_number('0.0004'),
                },
                'spot': {
                    'taker': self.parse_number('0.0004'),
                    'maker': self.parse_number('0.0004'),
                },
            },
            'requiredCredentials': {
                'apiKey': False,
                'secret': False,
                'walletAddress': True,
                'privateKey': True,
            },
            # options allows user to pass a signing helper (from Reya SDK) or a custom signer callback
            "options": {
                # signer: either an object with `sign_order(payload, path, method)` -> returns dict(headers)
                # or a callable: signer(payload, path, method) -> dict(headers)
                "signer": None,
                # account_id required for create-order if not supplied in call:
                "account_id": None,
                # control fetch_tickers concurrency (batch size). None -> full parallel
                "tickers_batch_size": None,
            },
        })

    def withClient(self, client:ReyaTradingClient):
        self.client:ReyaTradingClient = client


    # -------------------
    # Signing: call SDK signer only for private endpoints, TODO right now not working good
    # -------------------
    def sign(self, path: str, api: str = "public", method: str = "GET", params: Optional[Dict] = None, headers: Optional[Dict] = None, body: Optional[Any] = None):
        """
        Build URL, headers, body. For private endpoints call the signer supplied in options['signer'].
        The signer must return a dict of headers to attach (including signature and nonce if required).
        """
        params = params or {}
        headers = headers or {}
        url = self.urls["api"][api] + "/" + path.lstrip("/")

        if api == "public":
            # replace placeholders in path, e.g. /prices/{symbol}
            used_keys = []
            for k, v in params.items():
                placeholder = "{" + k + "}"
                if placeholder in url:
                    url = url.replace(placeholder, str(v))
                    used_keys.append(k)

            # remove used params
            for k in used_keys:
                params.pop(k, None)

            if method == "GET":
                if params:
                    url += "?" + self.urlencode(params)
                body = None
            else:
                body = self.json(params) if params else None
                headers["Content-Type"] = "application/json"

            return {
                "url": url,
                "method": method,
                "body": body,
                "headers": headers,
            }

        # private - require signing
        signer = self.safe_value(self.options, 'signer')
        # Accept either callable or object with sign_order(payload, path, method)
        payload = params or {}
        if body is not None:
            # if body was set by caller, prefer that
            try:
                payload = json.loads(body)
            except Exception:
                payload = body
        # Include account_id / wallet_address defaulting to options
        account_id = self.safe_value(self.options, "account_id")
        wallet_address = self.walletAddress
        if isinstance(payload, dict):
            if account_id and 'accountId' not in payload and 'account_id' not in payload and 'accountId' not in payload:
                payload.setdefault('accountId', account_id)
        # signer returns additional headers required by Reya (signature, timestamp, etc)
        headers.update({'Content-Type': 'application/json'})
        if signer is None:
            raise NotImplementedError("Private request signing requires a signer. Pass 'options': {'signer': signer_callable_or_object} when constructing the exchange. The signer should return a dict of headers (e.g. {'Reya-Timestamp':..., 'Reya-Signature':...}).")
        # call signer
        if callable(signer):
            extra_payload = signer(payload, path, method)
        else:
            # try object with sign_order or sign
            if hasattr(signer, "sign_order"):
                extra_payload = signer.sign_order(payload, path, method)
            elif hasattr(signer, "sign"):
                extra_payload = signer.sign(payload, path, method)
            else:
                raise NotImplementedError("Signer object requires a callable or a method named 'sign_order' or 'sign'.")
        if not isinstance(extra_payload, dict):
            raise TypeError("Signer must return a dict of headers.")
        payload.update(extra_payload)
        body = json.dumps(self.make_json_safe(payload)) if isinstance(payload, dict) else payload
        url = self.urls['api'][api] + '/' + path.lstrip('/')
        return {"url": url, "method": method, "body": body, "headers": headers}

    def make_json_safe(self, d):
        safe = {}
        for k, v in d.items():
            if isinstance(v, (str, int, float, bool, type(None), list, dict)):
                safe[k] = v
            elif hasattr(v, "value"):  # likely an Enum
                safe[k] = v.value
            else:
                safe[k] = str(v)  # last-resort: stringify
        return safe

    # -------------------
    # Helpers for parsing / mapping
    # -------------------
    def parse_ticker(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        ts = self.safe_integer(raw, 'timestamp', self.milliseconds())

        return {
            "timestamp": ts,
            "datetime": self.iso8601(ts),
            "high": self.safe_float(raw, 'high'),
            "low": self.safe_float(raw, 'low'),
            "bid": self.safe_float(raw, 'best_bid'),
            "ask": self.safe_float(raw, 'best_ask'),
            "last":self.safe_float(raw, 'poolPrice', 'price'),
            "baseVolume": self.safe_float(raw, 'volume', 'last24hVolume'), #todo from other endpoint
            "info": raw,
        }

    # def parse_orderbook(self, raw: Dict[str, Any]) -> Dict[str, Any]:
    #     ts = self.safe_integer(raw, 'timestamp', _now_ms())
    #     return {
    #         "bids": self.safe_value(raw, 'bids', []),
    #         "asks": self.safe_value(raw, 'asks', []),
    #         "timestamp": ts,
    #         "datetime": self.iso8601(ts),
    #         "nonce": self.safe_value(raw, 'nonce'),
    #         "info": raw,
    #     }

    def parse_trade(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        ts = self.safe_string(raw, 'timestamp')
        if ts is None:
            ts = _now_ms()
        else:
            # Parse ISO8601 (the "Z" means UTC)
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            # Milliseconds since epoch
            ts = int(dt.timestamp() * 1000)

        side = None
        if "side" in raw and raw.get("side") == "B":
            side = EOrderSide.BUY.value
        else:
            side = EOrderSide.SELL.value

        amount = self.safe_number_2(raw, 'qty', 'amount')

        price = self.safe_number(raw, 'price')

        return {
            "id": self.safe_string_2(raw, 'trade_id', 'id'),
            "timestamp": ts,
            "datetime": self.iso8601(ts),
            "symbol": self.safe_string_2(raw, 'symbol', 'ticker'),
            "price": price,
            "amount": amount,
            "side": side,
            "info": raw,
            "status": EOrderStatus.CLOSED.value
        }

    def parse_order(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        ts = self.safe_integer_2(raw, 'creation_timestamp_ms', 'created_at', _now_ms())
        if "side" in raw and raw.get("side") == "B":
            side = EOrderSide.BUY.value
        else:
            #Value A = Ask/Sell
            side = EOrderSide.SELL.value
        if "orderType" in raw and raw.get("orderType") == "LIMIT":
            type = EOrderType.LIMIT.value
        else:
            type = EOrderType.MARKET.value

        symbol = self.safe_string_2(raw, 'symbol', 'ticker')
        symbol = self.convertSymbolToCcxtNotation(symbol)

        status = raw.get('status').lower()
        return {
            "id": self.safe_string_2(raw, 'order_id', 'orderId'),
            "timestamp": ts,
            "datetime": self.iso8601(ts),
            "status": status,
            "symbol": symbol,
            "type": type,
            "side": side,
            "price": self.safe_value_2(raw, 'limitPx', 'triggerPx'),
            "amount": self.safe_value(raw, 'qty', 0),
            "filled": self.safe_value(raw, 'execQty', 0),
            "remaining": str(float(self.safe_value(raw, 'qty')) - float(self.safe_value(raw, 'execQty'))),
            "info": raw,
        }

    # -------------------
    # Public methods (ccxt names)
    # -------------------
    # def load_markets(self, reload: bool = False, params: Optional[Dict] = None) -> Dict[str, Any]:
    #     if self.markets and not reload:
    #         return self.markets
    #     res = self.publicGetApiMarkets(params or {})
    #     # the SDK/docs return a list of market objects
    #     markets = res if isinstance(res, list) else self.safe_value(res, 'data', res)
    #     self.markets = { self.safe_string(m, 'id', str(self.safe_integer(m,'market_id'))) : m for m in markets }
    #     self.markets_by_id = self.markets
    #     return self.markets

    def _getSymbol(self, perp_name):
        return perp_name.replace('RUSDPERP', '')

    def convertSymbolToCcxtNotation(self, symbol):
        if "/RUSD:RUSD" not in symbol:
            symbol = self._getSymbol(symbol)
            symbol = symbol + "/RUSD:RUSD"
        return symbol

    def convertSymbolToReyaNotation(self, symbol):
        if "RUSDPERP" not in symbol:
            symbol = symbol.replace("/RUSD:RUSD", "RUSDPERP")
        return symbol

    def _decimal_places(self, x):
        return int(-math.log10(float(x)))

    def fetch_markets(self, params: Optional[Dict] = None) -> List[Dict]:
        # [
        #     {
        #         "symbol": "BTCRUSDPERP",
        #         "marketId": 1,
        #         "minOrderQty": "0.001",
        #         "qtyStepSize": "0.001",
        #         "tickSize": "0.01",
        #         "liquidationMarginParameter": "0.05",
        #         "initialMarginParameter": "0.04",
        #         "maxLeverage": 40,
        #         "oiCap": "10000"
        #     }
        # ]
        res = self.publicGetApiMarkets(params or {})
        # the SDK/docs return a list of market objects
        result = res if isinstance(res, list) else self.safe_value(res, 'data', res)
        self.markets = {self.safe_string(m, 'id', str(self.safe_integer(m,'marketId'))) : m for m in result }
        self.markets_by_id = self.markets
        out = []
        for mid, m in self.markets.items():
            quoteToken = self._getSymbol(m.get("symbol"))
            underlyingAsset = "RUSD"
            out.append({
                'id': self.safe_string(m, 'marketId'),
                'symbol': f"{quoteToken}/{underlyingAsset}:{underlyingAsset}".upper(),
                'base': quoteToken.upper() if quoteToken is not None else '',
                'quote': underlyingAsset.upper() if underlyingAsset is not None else '',
                'asset_pair_id': self.safe_string_2(m, 'marketId', 'marketId'),
                'type': 'swap',
                'spot': False,
                'margin': False,
                'swap': True,
                'future': False,
                'option': False,
                'active': None,
                'precision': {'amount': self._decimal_places(m.get('tickSize'))},
                'limits': {'cost': {'min': 1}},
                'info': m,
            })
        return out

    def fetch_funding_rate(self, symbol: str, params: object = {}) -> FundingRate | None:
        self.load_markets(reload=True) #require reload because funding data is written there
        for sym, market in self.markets.items():
            if sym == symbol:
                request = {"symbol": self.convertSymbolToReyaNotation(symbol)}
                raw = self.public_get_api_market_summary(self.extend(request, params or {}))
                fr = self._parse_funding_rate(symbol, market["info"], raw)
                return fr

    def _parse_funding_rate(self, symbol, market, summary) -> FundingRate:
        # Summary
        # {
        #     "symbol": "BTCRUSDPERP",
        #     "updatedAt": 1747927089946,
        #     "longOiQty": "154.741",
        #     "shortOiQty": "154.706",
        #     "oiQty": "154.741",
        #     "fundingRate": "-0.000509373441021089",
        #     "longFundingValue": "412142.26",
        #     "shortFundingValue": "412142.26",
        #     "fundingRateVelocity": "-0.00000006243",
        #     "volume24h": "917833.49891",
        #     "pxChange24h": "92.6272285500004",
        #     "throttledOraclePrice": "2666.48162040777",
        #     "throttledPoolPrice": "2666.48166680625",
        #     "pricesUpdatedAt": 1747927089597
        # }
        #
        symbol = symbol
        funding = self.safe_number(summary, 'fundingRate')
        markPx = 0
        oraclePx = 0
        fundingTimestamp = (int(math.floor(self.milliseconds()) / 60 / 60 / 1000) + 1) * 60 * 60 * 1000

        return {
            'info': self.extend(market, summary),
            'symbol': symbol,
            'markPrice': markPx,
            'indexPrice': oraclePx,
            'interestRate': None,
            'estimatedSettlePrice': None,
            'timestamp': None,
            'datetime': None,
            'fundingRate': funding,
            'fundingTimestamp': fundingTimestamp,
            'fundingDatetime': self.iso8601(fundingTimestamp),
            'nextFundingRate': None,
            'nextFundingTimestamp': None,
            'nextFundingDatetime': None,
            'previousFundingRate': None,
            'previousFundingTimestamp': None,
            'previousFundingDatetime': None,
            'interval': '1h',
        }


    def fetch_ticker(self, symbol: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        self.load_markets()
        market = self.market(symbol)
        markTokenTicker = market['base'] + "RUSDPERP"

        request = {"symbol": markTokenTicker}
        raw = self.public_get_api_trading_prices(self.extend(request, params or {}))
        parsed = self.parse_ticker(raw)
        return parsed

    def fetch_tickers(self, symbols: Optional[List[str]] = None, params: Optional[Dict] = None) -> Dict[str, Dict]:
        raise NotImplementedError

    def fetch_order_book(self, symbol: str, limit: Optional[int] = 100, params: Optional[Dict] = None) -> Dict[str, Any]:
        raise NotImplementedError

    def fetch_ohlcv(self, symbol: str, timeframe='1m', since: Int = None, limit: Int = None, params={}) -> List[list]:
        exchange_delegate = ccxt.binance() # TODO espacialy for > 1D Timeframes?
        symbol = symbol.replace("RUSD", "USDT")
        return exchange_delegate.fetch_ohlcv(symbol, timeframe, since, limit, params)

    # TODO
    # def fetch_ohlcv(self, symbol: str, timeframe='1m', since: Int = None, limit: Int = None, params={}) -> List[list]:
    #     self.load_markets()
    #     market = self.market(symbol)
    #     markTokenTicker = market['base'] + "USDPERP"
    #
    #     timeframeOrig = timeframe
    #     if timeframe == "1w":
    #         exchange_delegate = ccxt.binance()  # delegate Reya has no Data on this timeframe available TODO better option?
    #         symbol = symbol.replace("RUSD", "USDT")
    #         return exchange_delegate.fetch_ohlcv(symbol, timeframe, since, limit, params)
    #     elif timeframe == "1M":
    #         exchange_delegate = ccxt.binance() # delegate Reya has no Data on this timeframe available TODO better option?
    #         symbol = symbol.replace("RUSD", "USDT")
    #         return exchange_delegate.fetch_ohlcv(symbol, timeframe, since, limit, params)
    #     request = {}
    #     request["symbol"] = markTokenTicker
    #     request["resolution"] = timeframe
    #
    #     raw = self.public_get_historical_candles(self.extend(request, params or {}))
    #
    #
    #     # map timeframe to seconds
    #     tf_map = {
    #         "1m": 60,
    #         "5m": 300,
    #         "1h": 3600,
    #         "2h": 7200,
    #         "4h": 14400,
    #         "12h": 43200,
    #         "1d": 86400,
    #         "1w": 86400 * 7, #umrechnung auf wochen
    #         "1M": 86400 * 7 * 4 #umrechnung auf monate
    #     }
    #
    #     if timeframeOrig not in tf_map and timeframeOrig != "1w":
    #         raise ValueError(f"Unsupported timeframe {timeframeOrig}")
    #     tf_sec = tf_map.get(timeframeOrig)
    #
    #     # delegation to binance
    #     # return delegate.fetch_ohlcv(symbol.replace("RUSD", "USDT"), timeframe, since, limit, params)
    #     path = f"api/trading/candles/{market['base']}{'USDMARK'}/{timeframe}"
    #     query = params or {}
    #     if limit is not None:
    #         limit = int(limit)
    #     else:
    #         limit = None
    #     if since:
    #         query['from'] = int( int(since) / 1000)
    #
    #         if limit:
    #             query['to'] = int((since + (limit * tf_sec * 1000)) / 1000)
    #         else:
    #             query['to'] = int(int(_now_ms()) / 1000)
    #     else:
    #         to = int(int(_now_ms()) / 1000)
    #         query['from'] = to - (limit * tf_sec)  # subtract seconds, not ms
    #         query['to'] = to
    #     if limit:
    #         query['limit'] = limit
    #
    #     raw = self.request(path, 'public', 'GET', query, None)
    #     # normalize response expected format -> list of candles
    #     data = raw.get('data', raw) if isinstance(raw, dict) else raw
    #
    #     # Assuming `data` is column-oriented dict:
    #     # {
    #     #   "time": [...],
    #     #   "open": [...],
    #     #   "high": [...],
    #     #   "low": [...],
    #     #   "close": [...],
    #     #   ...
    #     # }
    #     out = []
    #     for i in range(len(data["t"])):
    #         ohlcv = [
    #             int(int(data["t"][i]) * 1000),  # timestamp ms
    #             float(data["o"][i]),  # open
    #             float(data["h"][i]),  # high
    #             float(data["l"][i]),  # low
    #             float(data["c"][i]),  # close
    #             0,  # volume not avail
    #         ]
    #         out.append(ohlcv)
    #     # out = [data.get('time'), float(data.get('open')), float(data.get('high')), float(data.get('low')),
    #     #        float(data.get('close')), 0]
    #     return out
    #     #self.parse_ohlcvs(out, market, timeframe, since, limit)

    # def _fetch_single_ohlcv(self, symbol: str, timeframe='1m', since: Int = None, limit: Int = None, params={}) -> List[list]:
    #     # symbol expected to be assetPairId or known market symbol
    #     # https://api.reya.xyz/api/trading/candle/ETHUSDMARK/1
    #     self.load_markets()
    #     market = self.market(symbol)
    #
    #     if timeframe == '1m':
    #         timeframe = "1"
    #     elif timeframe == "1h":
    #         timeframe = "60"
    #     elif timeframe == "2h":
    #         timeframe = "120"
    #     elif timeframe == "5m":
    #         timeframe = "5"
    #     elif timeframe == "4h":
    #         timeframe = "240"
    #     elif timeframe == "12h":
    #         timeframe = "720"
    #     elif timeframe == "1d":
    #         timeframe = "1D"
    #     elif timeframe == "1w":
    #         raise UnsupportedOperation
    #
    #     # delegate = ccxt.binance()
    #     # delegate.load_markets()
    #
    #     # delegation to binance
    #     # return delegate.fetch_ohlcv(symbol.replace("RUSD", "USDT"), timeframe, since, limit, params)
    #     path = f"api/trading/candle/{market['base']}{'USDMARK'}/{timeframe}"
    #     query = params or {}
    #     if since:
    #         query['from'] = int(since / 1000)
    #     if limit:
    #         query['limit'] = int(limit)
    #     raw = self.request(path, 'public', 'GET', query, None)
    #     # normalize response expected format -> list of candles
    #     data = raw.get('data', raw) if isinstance(raw, dict) else raw
    #     out = [data.get('time'), float(data.get('open')), float(data.get('high')), float(data.get('low')),
    #            float(data.get('close')), 0]
    #     return out

    def fetch_balance(self, params: Optional[Dict] = None) -> Dict[str, Any]:
        request = {"wallet_address": self.walletAddress}
        balances = self.public_get_api_accounts_balance(self.extend(request, params or {}))
        # Try SRUSD first TODO ETH Value? Multi Accounts?
        balance = 0
        for entry in balances:
            if entry["asset"] == "SRUSD":
                balance += float(entry["realBalance"]) * 0.9 #staked only 90%, 10% haircut TODO
        for entry in balances:
            if entry["asset"] == "RUSD":
                balance += float(entry["realBalance"])

        # raw expected to be list of balances
        # calc used since api didnt support it
        openOrders = self.fetch_open_orders()
        levs = self.fetch_leverages()
        used = 0
        for openOrder in openOrders:
            amount = float(openOrder['amount'])
            price = float(openOrder['price'])
            value = (amount * price) / float(levs.get(openOrder['symbol'], 3))
            used += value

        bal = {"RUSD": {}}
        # only knows RUSD for Trading
        bal["RUSD"]['free'] = balance - used
        bal["RUSD"]['total'] = balance
        bal["RUSD"]['used'] = used
        return bal

    # OLD
    # def fetch_balance(self, params: Optional[Dict] = None) -> Dict[str, Any]:
    #
    #
    #     #TODO right now only RUSD (staked) and using old api v1
    #     rusd = '0xa9f32a851b1800742e47725da54a09a7ef2556a3'
    #     path = f"api/trading/wallet/{self.walletAddress}/accounts/balances"
    #     raw = self.request(path, 'public', 'GET', params or {}, None)
    #     # raw expected to be list of balances
    #     # calc used since api didnt support it
    #     openOrders = self.fetch_open_orders()
    #     used = 0
    #     for openOrder in openOrders:
    #         amount = float(openOrder['amount'])
    #         price = float(openOrder['price'])
    #         value = (amount * price) / float(self.fetch_leverage(openOrder['symbol']))
    #         used += value
    #
    #     balances = {'info': raw, 'free': {}, 'used': {}, 'total': {}}
    #     items = raw.get('data', raw) if isinstance(raw, dict) else raw
    #
    #     totalBalance = 0
    #     code = "RUSD"
    #     bal = {}
    #     bal[code] = {}
    #     for it in items:
    #         if it['collateral'] == rusd:
    #             total = float(it.get('balance'))
    #             total = float(Decimal(str(total)) / Decimal('1e18'))
    #             totalBalance += total
    #         else:
    #             # wir rechnen staked rusd nur mit 90%, 10% haircut
    #             total = float(it.get('balance')) * 0.9
    #             total = float(Decimal(str(total)) / Decimal('1e18'))
    #             totalBalance += total
    #     bal[code]['free'] = totalBalance - used
    #     bal[code]['total'] = totalBalance
    #     bal[code]['used'] = used
    #     return bal

    def set_margin_mode(self, marginMode: str, symbol: Str = None, params={}):
       return True #mock TODO

    lev_map = {}

    def fetch_leverage(self, symbol: str, params={}):
        # [
        #     {"accountId":"","marketId":"2","leverage":3,"createdAt":"2025-08-15T21:38:17.822Z","updatedAt":"2025-08-15T21:38:17.822Z"}
        # ]
        request = {"wallet_address": self.walletAddress}
        levs = self.public_get_leverages(self.extend(request, params or {}))
        if self.lev_map == {}:
            self.lev_map = {lev['marketId']: int(lev['leverage']) for lev in levs}

        market_id = None
        if symbol is not None:
            market = self.markets.get(symbol)
            if market is None:
                raise ccxt.ExchangeError(f"{self.id} fetch_leverage symbol {symbol} not found in markets")
            market_id = market.get('id') or market.get('market_id')

        return self.lev_map.get(market_id, 3)  # Default = 3

    def fetch_leverages(self, symbols: Strings = None, params={}):
        # [
        #     {"accountId":"","marketId":"2","leverage":3,"createdAt":"2025-08-15T21:38:17.822Z","updatedAt":"2025-08-15T21:38:17.822Z"}
        # ]
        request = {"wallet_address": self.walletAddress}
        levs = self.public_get_leverages(self.extend(request, params or {}))
        lev_map_by_id = {lev["marketId"]: int(lev["leverage"]) for lev in levs}

        symbol_lev_map = {}
        for symbol, market in self.markets.items():
            market_id = market.get("id") or market.get("market_id")
            if market_id in lev_map_by_id:
                symbol_lev_map[symbol] = lev_map_by_id[market_id]

        self.lev_map = symbol_lev_map

        # If a symbol (or list of symbols) was provided, return only those
        if symbols:
            if isinstance(symbols, str):
                symbols = [symbols]
            result = {}
            for sym in symbols:
                if sym not in self.markets:
                    raise ccxt.ExchangeError(f"{self.id} fetch_leverage symbol {sym} not found in markets")
                result[sym] = self.lev_map.get(sym, 3)  # Default = 3
            return result if len(result) > 1 else list(result.values())[0]

        # Otherwise return all leverages
        return self.lev_map

    def fetch_position(self, symbol: str, params={}):
        # [
        #     {
        #         "exchangeId": 1,
        #         "symbol": "BTCRUSDPERP",
        #         "accountId": 12345,
        #         "qty": "1.5",
        #         "side": "B",
        #         "avgEntryPrice": "43000.00",
        #         "avgEntryFundingValue": "100.25",
        #         "lastTradeSequenceNumber": 152954
        #     }
        # ]

        request = {"wallet_address": self.walletAddress}
        positions = self.public_get_positions(self.extend(request, params or {}))
        if positions is []:
            return []

        result = []
        for raw in positions:
            market_id = None
            if symbol is not None:
                market = self.markets.get(symbol)
                if market is None:
                    raise ccxt.ExchangeError(f"{self.id} fetch_order symbol {symbol} not found in markets")
                market_id = market.get('exchangeId') or market.get('exchangeId') or None
            if symbol is not None and market_id == raw.get('exchangeId'):
                base_multiplier = self.safe_number(raw, 'base_multiplier', 1)

                def safe_div(n, d):
                    return (n / d) if (n is not None and d not in (None, 0)) else None

                base_amount = self.safe_number(raw, 'qty')
                mark_price = self.fetch_ticker(symbol)['last']
                # #use avg price?
                last_price = self.safe_number(raw, 'last_price')
                # realized_pnl = safe_div(self.safe_number(raw, 'realized_pnl'), base_multiplier)
                funding_value = self.safe_number(raw, 'avgEntryFundingValue')
                # #avg_entry = safe_div(self.safe_number(raw, 'average_entry_funding_value'), base_multiplier)
                #
                # # session = int(self.safe_number(raw, 'session'))
                # # filledOrders = self.fetch_closed_orders(symbol=symbol)
                # # #für akt position relevant
                # # total_cost = 0.0
                # # total_qty = 0.0
                # # count = 0
                # # for filled in filledOrders:
                # #     if int(filled["info"]["position_session"]) == session and filled['side'] == EOrderSide.BUY.value:
                # #         filledPrice = float(filled["price"])
                # #         filledAmount = float(filled["amount"])
                # #         total_cost += filledPrice * filledAmount
                # #         total_qty += filledAmount
                # #         count += 1
                # # avg_entry = total_cost / total_qty if total_qty > 0 else None
                avg_entry = self.safe_number(raw, 'avgEntryPrice')

                pnl = base_amount * (mark_price - avg_entry)

                if funding_value < 0:
                    pnl = pnl + funding_value
                if base_amount == 0: #0er position manuell filter
                    continue

                leverage = self.fetch_leverage(symbol)
                liquidationPrice = avg_entry * (1 - 1/leverage)

                orders = self.fetch_open_orders(symbol)
                tp = 0
                sl = 0
                for order in orders:
                    if ("params" in order and "takeProfitPrice" in order['params']) or order['info']['order_type'] == "Take Profit":
                        tp = order['price']
                    if ("params" in order and "stopLossPrice" in order['params']) or order['info']['order_type'] == "Stop Loss":
                        sl = order['price']

                position = {
                    "size": base_amount,
                    "entryPrice": avg_entry,  # API doesn't give entry price, fallback to last_price
                    "lastPrice": mark_price,
                    "positionValue": base_amount * last_price if base_amount is not None and last_price is not None else None,
                    "unrealisedPnl": pnl,  # no unrealized from API, using realized for now
                    "takeProfit": tp,
                    "stopLoss": sl,
                    "liquidationPrice": liquidationPrice,
                    "fundingValue": funding_value,
                }

                safePosition = self.safe_position({
                    'info': raw,
                    'position': position,
                    'id': raw.get('unique_id'),
                    'symbol': symbol,
                    'timestamp': None,
                    'datetime': None,
                    'isolated': True,
                    'hedged': None,
                    'side': EOrderSide.BUY.value if raw.get('side') == 'B' else EOrderSide.SELL.value,
                    'contracts': position["size"],
                    'amount': position["size"],
                    'contractSize': None,
                    'entryPrice': position["entryPrice"],
                    'markPrice': mark_price,
                    'notional': position["positionValue"],
                    'leverage': leverage,
                    'collateral': 0,
                    'initialMargin': self.parse_number(1),
                    'maintenanceMargin': None,
                    'initialMarginPercentage': None,
                    'maintenanceMarginPercentage': None,
                    'unrealizedPnl': position["unrealisedPnl"],
                    'takeProfitPrice': position["takeProfit"],
                    'stopLossPrice': position["stopLoss"],
                    'liquidationPrice': position["liquidationPrice"],
                    'marginMode': False,
                    'percentage': self.parse_number(50),
                })

                result.append(safePosition)

        if symbol is None:
            return result
        else:
            for res in result:
                if res['symbol'] == symbol:
                    return res

    # -------------------
    # Private / wallet & orders
    # -------------------


    def create_order(self, symbol: str, type: str, side: str, amount: float, price: Optional[float] = None, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        TODO short order handling?
        Create an order via POST /api/trading/create-order.
        Required fields (per docs): accountId, marketId, exchangeId, isBuy, price, size, reduceOnly, type, signature, nonce, signerWallet
        The signer should provide signature/nonce/signerWallet via options['signer'] (or return headers).
        This method will attempt to fill accountId from options if not provided in params.
        """
        params = params or {}
        markets = self.load_markets()
        # map symbol to market_id/exchange_id/assetPairId if available
        market_id = params.get('marketId')
        exchange_id = REYA_DEX_ID
        for m in markets.values():
            if m.get('symbol') == symbol or str(m.get('id')) == str(symbol):
                market_id = market_id or m.get('id')
                exchange_id = exchange_id or m.get('exchange_id') or m.get('exchangeId') or exchange_id
                break
        account_id = params.get('accountId') or self.safe_value(self.options, 'account_id')
        if account_id is None:
            raise RuntimeError("create_order requires accountId either in params or options['account_id']")
        reduceOnly = False
        symbol = self.convertSymbolToReyaNotation(symbol)

        if type == EOrderType.LIMIT.value:
            time_in_force = TimeInForce.GTC
            limit_params = LimitOrderParameters(
                market_id=int(market_id) if market_id is not None else None,
                symbol=symbol,
                is_buy=True if side.lower() == 'buy' else False,
                limit_px=str(price) if price is not None else None,
                qty=str(amount),
                time_in_force=time_in_force,
                expires_after=params.get('expires_after')
            )
        else:
            time_in_force = TimeInForce.IOC
            limit_params = LimitOrderParameters(
                market_id=int(market_id) if market_id is not None else None,
                symbol=symbol,
                is_buy=True if side.lower() == 'buy' else False,
                limit_px=str(price) if price is not None else None,
                qty=str(amount),
                time_in_force=time_in_force,
                reduce_only=reduceOnly,
                expires_after=params.get('expires_after'))

        result = None
        if params is not None and params != {}:
            if "takeProfitPrice" in params:
                takeProfitPrice = params['takeProfitPrice']
                result:CreateOrderResponse = run_async(self.client.create_trigger_order(
                    TriggerOrderParameters(
                        market_id=int(market_id),
                        symbol=symbol,
                        is_buy=False,
                        trigger_px=str(takeProfitPrice),
                        trigger_type=OrderType.TP,
                    )
                ))
            elif "stopLossPrice" in params:
                stopLossPrice = params['stopLossPrice']
                result:CreateOrderResponse = run_async(self.client.create_trigger_order(
                    TriggerOrderParameters(
                        market_id=int(market_id),
                        symbol=symbol,
                        is_buy=False,
                        trigger_px=str(stopLossPrice),
                        trigger_type=OrderType.SL,
                    )
                ))
        else:
            result:CreateOrderResponse = run_async(self.client.create_limit_order(limit_params))

        id = None
        status = "open"
        if result is not None:
            id = result.order_id
            status = result.status


        return self.safe_order({ #TODO values
            'info': result,
            'id': id,
            'order':id,
            'clientOrderId': id,
            'timestamp': self.iso8601(int(time.time() * 1000)),
            'datetime':self.iso8601(int(time.time() * 1000)),
            'symbol': symbol,
            'type': type,
            'timeInForce': False,
            'postOnly': True,
            'reduceOnly': params.get('reduceOnly', False),
            'side':side,
            'price': price,
            'triggerPrice': price,
            'takeProfitPrice': None,
            'stopLossPrice': None,  # TODO exists?
            'amount': amount,
            'cost': None,
            'average': None,
            'filled': None,
            'remaining': None,
            'status': EOrderStatus.valueOf(status.lower()),
            'fee':
                {
                    'cost':0,
                    'currency': 'RUSD',
                    'rate': 0.004
                },
            'trades': []})

    def create_limit_order(self, symbol: str, side: OrderSide, amount: float, price: float, params={}):
        return self.create_order(symbol, EOrderType.LIMIT.value, side, amount, price, params)

    def create_market_order(self, symbol: str, side: OrderSide, amount: float, price: Num = None, params={}):
        return self.create_order(symbol, EOrderType.MARKET.value, side, amount, price, params)

    def cancel_order(self, id: str, symbol: Str = None, params={}):
        result:CancelOrderResponse = run_async(self.client.cancel_order(order_id=id))
        return result.status == "CANCELLED"


    def fetch_accounts(self, params={}):
        request = {"wallet_address": self.walletAddress}
        accounts = self.public_get_wallet_accounts(self.extend(request, params or {}))
        return accounts

    def fetch_order(self, id: str, symbol: str = None, params: Optional[Dict] = None):
        # [
        #     {
        #         "exchangeId": 1,
        #         "symbol": "BTCRUSDPERP",
        #         "accountId": 12345,
        #         "orderId": "123456789-123123123",
        #         "qty": "1.0",
        #         "execQty": "0.5",
        #         "side": "B",
        #         "limitPx": "43000.00",
        #         "orderType": "TP",
        #         "triggerPx": "50000.0",
        #         "timeInForce": "GTC",
        #         "reduceOnly": false,
        #         "status": "OPEN",
        #         "createdAt": 1747927089946,
        #         "lastUpdateAt": 1747927089946
        #     }
        # ]
        request = {"wallet_address": self.walletAddress}
        items = self.public_get_open_orders(self.extend(request, params or {}))
        symbol = self.convertSymbolToReyaNotation(symbol)
        for item in items:
            order_id = str(item.get('order_id') or item.get('orderId') or item.get('id'))
            if order_id != str(id):
                continue
            if symbol is None:
                return self.parse_order(item)
            if symbol == item['symbol']:
                return self.parse_order(item)
        raise ccxt.OrderNotFound(self.id + " fetch_order could not find order id " + str(id))

    def fetch_orders(self, symbol: Optional[str] = None, since: Optional[int] = None, limit: Optional[int] = None,
                     params: Optional[Dict] = None) -> List[Dict]:
        request = {"wallet_address": self.walletAddress}
        items = self.public_get_open_orders(self.extend(request, params or {}))
        items2 = self.fetch_my_trades(symbol=symbol, since=since, limit=limit, params=params)
        items2 = [trade['info'] for trade in items2]

        # Filter by symbol if provided
        if symbol is not None:
            market = self.markets.get(symbol)
            if market is None:
                raise ccxt.ExchangeError(f"{self.id} fetch_orders symbol {symbol} not found in markets")
            market_id = market.get('id') or market.get('market_id') or None
            filteredOrders = []
            for item in items:
                order_market_id = item.get('market_id') or item.get('marketId') or None
                if order_market_id is not None and str(order_market_id) == str(market_id):
                    item['symbol'] = symbol
                    filteredOrders.append(item)
            filteredTrades = []
            for item in items2:
                order_market_id = item.get('market_id') or item.get('marketId') or None
                if order_market_id is not None and str(order_market_id) == str(market_id):
                    item['symbol'] = symbol
                    filteredTrades.append(item)
            items2 = filteredTrades

        return [self.parse_order(o) for o in items] +  [self.parse_trade(o) for o in items2]

    def fetch_open_orders(self, symbol: Optional[str] = None, since: Optional[int] = None, limit: Optional[int] = None,
                          params: Optional[Dict] = None) -> List[Dict]:
        request = {"wallet_address": self.walletAddress}
        items = self.public_get_open_orders(self.extend(request, params or {}))

        # Filter by symbol if provided
        if symbol is not None:
            market = self.markets.get(symbol)
            if market is None:
                raise ccxt.ExchangeError(f"{self.id} fetch_orders symbol {symbol} not found in markets")
            market_id = market.get('id') or market.get('market_id') or None
            filteredOrders = []
            for item in items:
                order_market_id = item.get('market_id') or item.get('marketId') or None
                if order_market_id is not None and str(order_market_id) == str(market_id):
                    item['symbol'] = symbol
                    filteredOrders.append(item)
            return [self.parse_order(o) for o in filteredOrders]
        return [self.parse_order(o) for o in items]

    def fetch_my_trades(self, symbol: Optional[str] = None, since: Optional[int] = None, limit: Optional[int] = None,
                        params: Optional[Dict] = None) -> List[Dict]:
        #TODO start end time filtering
        params = params or {}

        request = {"wallet_address": self.walletAddress}
        items = self.public_get_open_orders(self.extend(request, params or {}))

        # Filter by symbol if provided
        if symbol is not None:
            market = self.markets.get(symbol)
            if market is None:
                raise ccxt.ExchangeError(f"{self.id} fetch_my_trades symbol {symbol} not found in markets")
            market_id = market.get('id') or market.get('market_id') or None
            filtered = []
            for t in items:
                trade_market_id = t.get('market_id') or t.get('marketId') or None
                if trade_market_id is not None and str(trade_market_id) == str(market_id):
                    t['symbol'] = symbol
                    filtered.append(t)
            items = filtered

        return [self.parse_trade(t) for t in items]

    def fetch_trades(self, symbol: str, since: Optional[int] = None, limit: Optional[int] = None,
                     params: Optional[Dict] = None) -> List[Dict]:
        markets = self.load_markets()
        market_id = None
        for m in markets.values():
            if m.get('symbol') == symbol or str(m.get('id')) == str(symbol):
                market_id = m.get('id')
                break
        if market_id is None:
            raise ccxt.ExchangeError(f"{self.id} fetch_trades could not find market id for symbol {symbol}")

        request = {"wallet_address": self.walletAddress}
        items = self.public_get_open_orders(self.extend(request, params or {}))

        # Apply since and limit client-side if needed:
        if since is not None:
            items = [t for t in items if t.get('timestamp', 0) >= since]
        if limit is not None:
            items = items[:limit]

        for i in items:
            i['symbol'] = symbol
        return [self.parse_trade(t) for t in items]

    # deposit / withdraw (wallet endpoints)
    def fetch_deposit_address(self, code: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        wallet_address = self.safe_value(self.options, 'wallet_address')
        if wallet_address is None:
            raise RuntimeError("fetch_deposit_address requires options['wallet_address']")
        path = f"api/trading/wallet/{wallet_address}/deposit-address"
        res = self.request(path, 'private', 'GET', params or {}, None)
        return res

    def withdraw(self, code: str, amount: float, address: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        wallet_address = self.safe_value(self.options, 'wallet_address')
        if wallet_address is None:
            raise RuntimeError("withdraw requires options['wallet_address']")
        body = {"currency": code, "amount": str(amount), "address": address}
        body.update(params or {})
        signed = self.sign("api/trading/wallet/withdraw", "private", "POST", body, None, None)
        return self.request("api/trading/wallet/withdraw", 'private', 'POST', body, signed['headers'])

    def get_current_stake_apy(self):
        request = {"pool_id": 1}
        return self.public_apy(request)

    def close(self):
        return run_async(self.client.close())