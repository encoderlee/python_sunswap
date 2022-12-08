import time
from decimal import Decimal
from typing import List
from datetime import datetime, timedelta
import os
from dataclasses import dataclass
from tronpy import Tron
from tronpy.keys import PrivateKey
from tronpy.providers import HTTPProvider


@dataclass
class Contract:
    symbol: str
    address: str
    decimals: int = None


class Known:
    usdt = Contract("USDT", "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t", 6)
    sun = Contract("SUN", "TSSMHYeV2uE9qYH95DqyoCuNCzEL1NvU3S", 18)
    sunswap = Contract("SunswapV2Router02", "TKzxdSv2FZKQrEqkKVgp5DcwEXBEKMg2Ax")


class SunSwap:

    def __init__(self, address_wallet: str, private_key: str = None):
        self.wallet: str = address_wallet
        provider = HTTPProvider(timeout=30, api_key="b0ed0858-e287-45be-beec-57c6cb509c46")
        provider.sess.trust_env = False
        self.tron = Tron(provider)
        self.private_key = PrivateKey(bytes.fromhex(private_key))

    # get ERC20 token balance of the account
    def erc20_balance(self, erc20: Contract) -> Decimal:
        contract = self.tron.get_contract(erc20.address)
        # get the token decimals if not
        decimals = erc20.decimals
        if not decimals:
            decimals = contract.functions.decimals()
        #  get the balance of tokens and convert it
        balance = contract.functions.balanceOf(self.wallet)
        balance = Decimal(balance) / (10 ** decimals)
        return balance

    # approve the sunswap contract to use erc20 tokens
    def approve_erc20_to_sunswap(self, erc20: Contract):
        contract = self.tron.get_contract(erc20.address)
        approve_amount = 2 ** 256 - 1
        amount = contract.functions.allowance(self.wallet, Known.sunswap.address)
        if amount >= approve_amount / 2:
            print("already approved")
            return None
        txn = (
            contract.functions.approve(Known.sunswap.address, approve_amount)
            .with_owner(self.wallet)
            .fee_limit(100 * 1000000)
            .build()
            .sign(self.private_key)
        )
        result = txn.broadcast().wait()
        if result["receipt"]["result"] == "SUCCESS":
            print("transaction ok: {0}".format(result))
        else:
            print("transaction error: {0}".format(result))
        return result

    # query the price of token pair
    def query_price(self, token_path: List[Contract]) -> Decimal:
        contract = self.tron.get_contract(Known.sunswap.address)
        path = [item.address for item in token_path]
        amount = contract.functions.getAmountsOut(1 * 10 ** token_path[0].decimals, path)
        amount_in = Decimal(amount[0]) / (10 ** token_path[0].decimals)
        amount_out = Decimal(amount[1]) / (10 ** token_path[-1].decimals)
        return amount_in / amount_out

    # swap token
    def swap_token(self, amount_in: Decimal, token_path: List[Contract]):
        # approve token to sunswap if not
        self.approve_erc20_to_sunswap(token_path[0])

        contract = self.tron.get_contract(Known.sunswap.address)
        path = [item.address for item in token_path]

        amount_in = int(amount_in * 10 ** token_path[0].decimals)
        amount = contract.functions.getAmountsOut(amount_in, path)
        # slippage 0.5% fee 0.3% ，minimum received 99.2 %
        minimum_out = int(amount[1] * (1 - Decimal("0.005") - Decimal("0.003")))
        deadline = datetime.now() + timedelta(minutes=5)
        txn = (contract.functions.swapExactTokensForTokens(amount_in, minimum_out, path, self.wallet,
                                                           int(deadline.timestamp()))
               .with_owner(self.wallet)
               .fee_limit(100 * 1000000)
               .build()
               .sign(self.private_key)
               )
        result = txn.broadcast().wait()
        if result["receipt"]["result"] == "SUCCESS":
            print("transaction ok: {0}".format(result))
        else:
            print("transaction error: {0}".format(result))
        return result


def main():
    # change it to your wallet address
    address_wallet = "TGrDfWjBrefFdsT6VNB4ZpN9qBpmfM6Smo"
    # set your private key to the environment variable 'key'
    private_key = os.getenv("key")
    sunswap = SunSwap(address_wallet, private_key)

    balance = sunswap.erc20_balance(Known.usdt)
    print("usdt balance: {0}".format(balance))

    limit_price = Decimal("0.0054")
    amount_buy = Decimal(1)
    print("if the price of SUN is lower than {0} USDT/SUN, buy {1} USDT of SUN".format(limit_price, amount_buy))

    token_path = [Known.usdt, Known.sun]

    while True:
        price = sunswap.query_price(token_path)
        print("sun price: {0} USDT/SUN".format(price))
        if price <= limit_price:
            print("price ok, buy {0} USDT of SUN".format(amount_buy))
            sunswap.swap_token(amount_buy, token_path)
            break
        time.sleep(2)


if __name__ == '__main__':
    main()
