from pathlib import Path
import yaml

from brownie import Vault, accounts, network, web3, Wei, interface, YearnDaiCompStratV2
from eth_utils import is_checksum_address

def main():
    dai = interface.ERC20('0x6b175474e89094c44da98b954eedeac495271d0f')
    old_strategy = YearnDaiCompStratV2.at('0x5b62F24581Ea4bc6d6C5C101DD2Ae7233E422884')
    live_strategy = YearnDaiCompStratV2.at('0x4C6e9d7E5d69429100Fcc8afB25Ea980065e2773')
    vault =  Vault.at('0x9B142C2CDAb89941E9dcd0B6C1cf6dEa378A8D7C')

    print(f'strategy YearnDaiCompStratV2: {live_strategy.address}')
    print(f'Vault: {vault.address}')
    print(f'Vault name: {vault.name()} and symbol: {vault.symbol()}')
    strategist_confirmed = live_strategy.strategist()
    print(f'Strategy strategist: {strategist_confirmed}')

    account_name = input(f"What account to use?: ")
    dev = accounts.load(account_name)
    print(f"You are using: 'dev' [{dev.address}]")
    devDai = dai.balanceOf(dev).to('ether')
    print(f"You're DAI balance is: [{devDai}]")
    are_you_strategist = strategist_confirmed == dev.address
    print(f"Are you strategist? {are_you_strategist}")

    if input("Continue? y/[N]: ").lower() != "y":
        return

    vault.migrateStrategy(old_strategy, live_strategy, {"from": dev, 'gas_price':Wei("25 gwei")})


    print('migrate time')
    if input("Continue? y/[N]: ").lower() != "y":
        return
   
    live_strategy.harvest({"from": dev, 'gas_price':Wei("25 gwei")})