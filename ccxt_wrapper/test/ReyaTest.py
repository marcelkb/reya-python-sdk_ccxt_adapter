import logging

from dotenv import load_dotenv

from ccxt_wrapper.Reya import Reya
from ccxt_wrapper.const import EOrderSide, EOrderType
from sdk.reya_rest_api import TradingConfig, ReyaTradingClient


# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def main():
    load_dotenv()
    config = TradingConfig.from_env()

    #signer = ReyaSignerAdapter(private_key = config.private_key, wallet_address=config.wallet_address, account_id=config.account_id, chain_id=config.chain_id) TODO not working right now
    exchange = Reya({
        'walletAddress': config.wallet_address,
        'privateKey': config.private_key,
        'options':{'account_id': config.account_id},
        'verbose': True,
    })
    client = ReyaTradingClient()
    exchange.withClient(client)
    symbol = 'SOL/RUSD:RUSD'  # market symbol

    ORDER_PLACEMENT = True
    AMOUNT = 0.1

    # load markets
    exchange.load_markets()

    # # Fetch the latest ticker for the symbol
    # print(f"Fetching ticker for {symbol}")
    ticker = exchange.fetch_ticker(symbol)
    print(f"{symbol} price: {ticker['last']}")
    funding = exchange.fetch_funding_rate(symbol)
    print(
        f"funding rate for {funding['symbol']}: {funding['info']['fundingRate']}@{funding['interval']} , lastTime: {funding['fundingDatetime']}, yearly: {funding['info']['fundingRateAnnualized']}%")
    funding = exchange.fetch_funding_rate("BTC/RUSD:RUSD")
    print(
        f"funding rate for {funding['info']['symbol']}: {funding['info']['fundingRate']}@{funding['interval']} , lastTime: {funding['fundingDatetime']}, yearly: {funding['info']['fundingRateAnnualized']}%")
    position = exchange.fetch_position(symbol)
    print(f"{position['info']['unrealisedPnl']} {position['info']['curRealisedPnl']} {position['info']['size']}")
    print(exchange.fetch_open_orders(symbol))

    # test sell

    #
    # # Fetch all open orders for the symbol
    # print(f"Fetching open orders for {symbol}")
    # orders = exchange.fetch_open_orders(symbol)
    #
    # # Loop through each open order and cancel it
    # for order in orders:
    #     print(f"Canceling order {order['id']} for {order['symbol']}")
    #     exchange.cancel_order(order["id"])
    #
    # # Fetch OHLCV (candlestick) data
    # print(f"Fetching OHLCV data for {symbol}")
    # print(exchange.fetch_ohlcv(symbol))

    # Fetch balance
    # print("Fetching account balance")
    # print(exchange.fetch_balance())

    # Fetch current open position
    # print(f"Fetching position for {symbol}")
    # print(exchange.fetch_position(symbol))

    # Fetch all currently open orders
    # print("Fetching all open orders")
    # print(exchange.fetch_open_orders())

    if ORDER_PLACEMENT:
        # Create a new limit order
        print(f"Creating LIMIT BUY order for {symbol}")
        print(exchange.create_order(symbol, EOrderType.LIMIT.value, EOrderSide.BUY.value, AMOUNT, ticker['last'] * 0.5))
    #
    # # Fetch currencies
    # print("Fetching currencies")
    # print(exchange.fetch_currencies())

    # Fetch markets
    # print("Fetching markets")
    # print(exchange.fetch_markets())
    #
    # # Fetch funding rate
    # print(f"Fetching funding rate for {symbol}")
    # print(exchange.fetch_funding_rate(symbol))

    if ORDER_PLACEMENT:
        # Create another limit order
        print(f"Creating another LIMIT BUY order for {symbol}")
        result = exchange.create_order(symbol, EOrderType.LIMIT.value, EOrderSide.BUY.value, AMOUNT, ticker['last'] * 0.5)

    # Fetch updated balance
    print("Fetching updated balance after order placement")
    print(exchange.fetch_balance())

    if ORDER_PLACEMENT:
        # Fetch details of created order
        print(f"Fetching details for order {result['id']}")
        print(exchange.fetch_order(result['id'], symbol))

    # Fetch all orders
    # print(f"Fetching all orders for {symbol}")
    # print(exchange.fetch_orders(symbol))

    # Cancel all fetched orders
    print(f"Canceling all fetched orders for {symbol}")
    orders = exchange.fetch_orders(symbol)
    for order in orders:
        print(f"Canceling order {order['id']}")
        result = exchange.cancel_order(order["id"])
        print(result)

    # Fetch open orders again
    print("Fetching open orders after cancellations")
    print(exchange.fetch_open_orders())

    # Fetch closed orders
    print("Fetching closed orders")
    print(exchange.fetch_closed_orders())

    # Fetch canceled + closed orders (not supported right now)
    #print("Fetching canceled and closed orders")
    #print(exchange.fetch_canceled_and_closed_orders())
    #
    # # Fetch trade history
    # print(f"Fetching trades for {symbol}")
    # print(exchange.fetch_trades(symbol))
    #
    # # Fetch my trades
    # print("Fetching my trades")
    # print(exchange.fetch_my_trades())
    #
    # # Fetch current position
    # print(f"Fetching current position for {symbol}")
    # print(exchange.fetch_position(symbol))

    # Set leverage (not supported right now)
    #print(f"Setting leverage for {symbol}")
    #print(exchange.set_leverage(symbol))

    if ORDER_PLACEMENT:
        # Create market and limit orders
        print(f"Creating MARKET BUY order for {symbol}")
        print(exchange.create_market_order(symbol, EOrderSide.BUY.value, AMOUNT, ticker['last'] * 1.01))

        print(f"Creating LIMIT BUY order for {symbol}")
        print(exchange.create_limit_order(symbol, EOrderSide.BUY.value, AMOUNT, ticker['last'] * 0.5))

    # Fetch leverage
    # print(f"Fetching leverage for {symbol}")
    # print(exchange.fetch_leverage(symbol))

    if ORDER_PLACEMENT:
        # Create TP order
        print(f"Creating TAKE PROFIT MARKET SELL order for {symbol}")
        print(exchange.create_order(
            symbol,
            EOrderType.MARKET.value,
            EOrderSide.SELL.value,
            AMOUNT,
            ticker['last'] * 1.01,
            params={'takeProfitPrice': '250', 'reduceOnly': True}
        ))

        # Create SL order
        print(f"Creating STOP LOSS MARKET SELL order for {symbol}")
        print(exchange.create_order(
            symbol,
            EOrderType.MARKET.value,
            EOrderSide.SELL.value,
            AMOUNT,
            ticker['last'] * 1.01,
            params={'stopLossPrice': '100', 'reduceOnly': True}
        ))

    # Fetch accounts
    # print("Fetching accounts")
    # print(exchange.fetch_accounts())

    exchange.close()

if __name__ == '__main__':
    main()
