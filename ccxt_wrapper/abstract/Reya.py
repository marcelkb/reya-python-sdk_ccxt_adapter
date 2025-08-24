from ccxt.base.types import Entry


class ImplicitAPI:
    # Public GET endpoints
    public_get_api_markets = publicGetApiMarkets = Entry('api/markets', 'public', 'GET', {'cost': 1})
    public_get_api_trading_prices = publicGetApiTradingPrices = Entry(
        'api/trading/prices', 'public', 'GET', {'cost': 1})
    public_get_api_orderbook_marketid = publicGetApiOrderbookMarketId = Entry('api/orderbook/{marketId}',
                                                                                   'public', 'GET', {'cost': 1})
    public_get_api_trades_marketid = publicGetApiTradesMarketId = Entry('api/trades/{marketId}', 'public',
                                                                             'GET', {'cost': 1})
    public_get_api_tickers = publicGetApiTickers = Entry('api/tickers', 'public', 'GET', {'cost': 1})
    public_get_api_tickers_marketid = publicGetApiTickersMarketId = Entry('api/tickers/{marketId}', 'public',
                                                                               'GET', {'cost': 1})

    # Private GET endpoints
    private_get_api_accounts_balance = privateGetApiAccountsBalance = Entry('api/accounts/balance', 'private',
                                                                                 'GET', {'cost': 1})
    private_get_api_orders_open = privateGetApiOrdersOpen = Entry('api/orders/open', 'private', 'GET',
                                                                       {'cost': 1})
    private_get_api_orders_history = privateGetApiOrdersHistory = Entry('api/orders/history', 'private', 'GET',
                                                                             {'cost': 1})
    private_get_api_orders_pair = privateGetApiOrdersPair = Entry('api/orders/{pair}', 'private', 'GET',
                                                                       {'cost': 1})
    private_get_api_orders_pair_orderid = privateGetApiOrdersPairOrderId = Entry('api/orders/{pair}/{orderId}',
                                                                                      'private', 'GET', {'cost': 1})
    private_get_api_wallet_deposithistory_currency = privateGetApiWalletDepositHistoryCurrency = Entry(
        'api/wallet/depositHistory/{currency}', 'private', 'GET', {'cost': 1})
    private_get_api_wallet_withdrawhistory_currency = privateGetApiWalletWithdrawHistoryCurrency = Entry(
        'api/wallet/withdrawHistory/{currency}', 'private', 'GET', {'cost': 1})

    # Private POST endpoints
    private_post_api_orders = privatePostApiOrders = Entry('api/orders', 'private', 'POST', {'cost': 1})
    private_post_api_orders_batch = privatePostApiOrdersBatch = Entry('api/orders/batch', 'private', 'POST',
                                                                           {'cost': 5})
    private_post_api_wallet_withdraw_currency = privatePostApiWalletWithdrawCurrency = Entry(
        'api/wallet/withdraw/{currency}', 'private', 'POST', {'cost': 10})

    # Private PUT endpoints
    private_put_api_orders = privatePutApiOrders = Entry('api/orders', 'private', 'PUT', {'cost': 5})

    # Private DELETE endpoints
    private_delete_api_orders_pair_orderid = privateDeleteApiOrdersPairOrderId = Entry(
        'api/orders/{pair}/{orderId}', 'private', 'DELETE', {'cost': 1})
    private_delete_api_orders_all = privateDeleteApiOrdersAll = Entry('api/orders/all', 'private', 'DELETE',
                                                                           {'cost': 5})
    private_delete_api_orders_pair = privateDeleteApiOrdersPair = Entry('api/orders/{pair}', 'private',
                                                                             'DELETE', {'cost': 5})
