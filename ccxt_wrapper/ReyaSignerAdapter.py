
from sdk import ReyaTradingClient, TradingConfig
from sdk.reya_rest_api.auth import SignatureGenerator
from sdk.reya_rest_api.constants.enums import TimeInForce, LimitOrderType, OrdersGatewayOrderType, Limit
import time

TESTNET = 89346162
MAINNET = 1729


'''
Not working right now, to be less dependend on the phyton sdk of reha, this adapter should do the auth sign logic independent.
'''
class ReyaSignerAdapter:
    def __init__(self, private_key = 'privatekey', wallet_address='walletaddress', account_id=123, chain_id=TESTNET):
        self.config = TradingConfig(
            api_url="https://api.reya.xyz/",
            chain_id=chain_id,
            private_key=private_key,
            account_id=account_id,
            wallet_address=wallet_address
        )
        self.signature_generator = SignatureGenerator(self.config)


    def sign_order(self, payload, path, method):
        signature = None
        nonce = None
        order_type = {}
        deadline = None

        order_type = {
            "limit": {
                "timeInForce": "IOC"
            }
        }

        if "createOrder" in path:
            # Generate nonce and deadline
            nonce = self.signature_generator.create_orders_gateway_nonce(self.config.account_id, self.config.account_id,
                                                                         int(time.time_ns() / 1000000))  # ms since epoch (int(time.time())
            deadline = self.signature_generator.get_default_expires_after(payload["expires_after"])

            inputs = self.signature_generator.encode_inputs_limit_order(
                is_buy=payload['is_buy'],
                limit_price=payload['price'],
                order_base=payload['size'],
            )
            order_type = LimitOrderType(limit=Limit(time_in_force=TimeInForce.IOC))
            order_type_sig = self.get_limit_order_gateway_type(payload["order_type"], payload["reduce_only"])
            signature = self.signature_generator.sign_raw_order(
                account_id=payload['accountId'],
                market_id=payload['market_id'],
                exchange_id=self.config.dex_id,
                counterparty_account_ids=[self.config.pool_account_id],
                order_type=order_type_sig,
                inputs=inputs,
                deadline=deadline,
                nonce=nonce,
            )

        return  {"signature": signature, "nonce":str(nonce),  "expiresAfter": deadline, "signerWallet":self.config.wallet_address, "type": order_type.to_dict(),"marketId": payload["market_id"], "reduceOnly": payload["reduce_only"], "isBuy": payload["is_buy"], "exchangeId": self.config.dex_id}


    def get_limit_order_gateway_type(self, order_type: LimitOrderType, reduce_only: bool) -> OrdersGatewayOrderType:
        # if order_type.limit.time_in_force == TimeInForce.IOC:
        #     return OrdersGatewayOrderType.REDUCE_ONLY_MARKET_ORDER if reduce_only else OrdersGatewayOrderType.MARKET_ORDER
        # else:
            return OrdersGatewayOrderType.LIMIT_ORDER
