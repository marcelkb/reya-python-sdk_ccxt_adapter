from ccxt.base.types import Entry


class ImplicitAPI:
    # Public GET endpoints
    public_get_api_markets = publicGetApiMarkets = Entry('v2/marketDefinitions', 'public', 'GET', {'cost': 1})
    public_get_api_trading_prices = publicGetApiTradingPrices = Entry('v2/prices/{symbol}', 'public', 'GET', {'cost': 1})
    public_get_api_market_summary = publicGetApiMarketSummary = Entry('v2/market/{symbol}/summary', 'public', 'GET', {'cost': 1})
    public_get_historical_candles = publicGetHistoricalCandles = Entry('v2/candleHistory/{symbol}/{resolution}', 'public', 'GET', {'cost': 1})
    public_get_positions = publicGetPositions = Entry('v2/wallet/{wallet_address}/positions', 'public', 'GET', {'cost': 1})
    public_get_api_accounts_balance = publicGetApiAccountsBalance = Entry('v2/wallet/{wallet_address}/accountBalances', 'public',
                                                                                 'GET', {'cost': 1})

    public_get_wallet_accounts = publicGetApiWalletAccounts = Entry('v2/wallet/{wallet_address}/accounts', 'public',
                                                                    'GET', {'cost': 1})

    public_get_open_orders = publicGetApiOpenOrders = Entry('v2/wallet/{wallet_address}/openOrders', 'public',
                                                                    'GET', {'cost': 1})


    public_get_trades = publicGetApiTrades = Entry('v2/wallet/{wallet_address}/perpExecutions', 'public',
                                                                    'GET', {'cost': 1})

    # old api no new api yet
    public_get_leverages = publicGetLeverages = Entry('api/trading/wallet/{wallet_address}/leverages', 'public', 'GET', {'cost': 1})
    public_apy = publicGetAPY = Entry('api/trading/poolBalance/{pool_id}', 'public', 'GET',
                                                      {'cost': 1})

    #old api
    public_get_api_accounts_balance_v1 = publicGetApiAccountsBalanceV1 = Entry('api/accounts/balance', 'public',
                                                                                 'GET', {'cost': 1})

    # Private GET endpoints




