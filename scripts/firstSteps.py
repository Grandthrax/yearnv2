from pathlib import Path
import yaml

from brownie import Token, Vault, accounts, network, web3, Wei, interface, YearnDaiCompStratV2
from eth_utils import is_checksum_address

def main():
    dai = interface.ERC20('0x6b175474e89094c44da98b954eedeac495271d0f')
    strategy = YearnDaiCompStratV2.at('0xEb1E2e30944797232C623498c546565a085B0623')
    vault =  Vault.at('0xc2cFcfa978a7fae529DC7E9Aa3CDBE7A727452Bc')

    print(f'strategy YearnDaiCompStratV2: {strategy.address}')
    print(f'Vault: {vault.address}')
    print(f'Vault name: {vault.name()} and symbol: {vault.symbol()}')
    strategist_confirmed = strategy.strategist()
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

    deposit_limit = Wei('100000 ether')
    deposit_limit_eth = deposit_limit.to('ether')

    if input(f"Set deposit limit to: {deposit_limit_eth}?").lower() != "y":
        return

    vault.setDepositLimit(deposit_limit, {"from": dev, 'gas_price':Wei("22 gwei")})

    if input(f"Add strategy: {strategy} ?").lower() != "y":
        return
    
    vault.addStrategy(strategy, deposit_limit, deposit_limit, 50, {"from": dev, 'gas_price':Wei("22 gwei")})

    amount = Wei('500 ether')
    amountE = amount.to('ether')
    
    if input(f"approve: {amountE} DAI?").lower() != "y":
        return
    dai.approve(vault, amount*100, {"from": dev, 'gas_price':Wei("22 gwei")})
    
    print('deposit amount:', amount.to('ether'))
    if input("Continue? y/[N]: ").lower() != "y":
        return
    vault.deposit(amount, {"from": dev, 'gas_price':Wei("19 gwei")})    

    print('harvest time')
    if input("Continue? y/[N]: ").lower() != "y":
        return
   
    strategy.harvest({"from": dev, 'gas_price':Wei("17 gwei")})