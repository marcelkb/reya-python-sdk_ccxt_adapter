# Reya CCXT Adapter 
This repository contains a fork of the Reya Python SDK for interacting with the Reya ecosystem. It provides tools for subscribing to the Reya WebSocket for market data updates and executing on-chain actions via RPC.

It adds an CCXT Wrapper purely phyton based by using the direct request calls for public methods and the SDK for private one to map to the interface methods of the ccxt environment.

Right now not all methods functions probably and it more like a POC.
 - fetchOHLCV delegates to Binance since Reya only support candles up to 1D-Timeframe and no easy management for calling last X Candles. Start und End Time is needed every time. Additonally the api is not as fast for complicated calculations based on a lot of candles.
 - The Signer for Private calls is not finished, so it relays on the SDK functions.
 - fetchBalance only recognized staked RUSD (0xa9f32a851b1800742e47725da54a09a7ef2556a3). Different Tokens for Collateral are not supported right now (wrtETH f.e.)
 - fetch_markets only supports ETH and BTC because it maps hard the ids from reya
 - fetch_canceled_and_closed_orders not supported right now
 - setLeverage not supported right now (no reya api endpoint)
