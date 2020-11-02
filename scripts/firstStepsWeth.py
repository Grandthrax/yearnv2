from pathlib import Path
import yaml

from brownie import Token, Vault, accounts, network, web3, Wei, interface, YearnWethCreamStratV2
from eth_utils import is_checksum_address

def main():
    dai = interface.ERC20('0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2')
    strategy = YearnWethCreamStratV2.at('0x97785a81B3505Ea9026b2aFFa709dfd0C9Ef24f6')
    vault =  Vault.at('0xf20731f26e98516dd83bb645dd757d33826a37b5')

    print(f'strategy YearnWethCreamStratV2: {strategy.address}')
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

    deposit_limit = Wei('500 ether')
    deposit_limit_eth = deposit_limit.to('ether')

    if input(f"Set deposit limit to: {deposit_limit_eth}?").lower() != "y":
        return

   # vault.setDepositLimit(deposit_limit, {"from": dev, 'gas_price':Wei("17 gwei")})

    if input(f"Add strategy: {strategy} ?").lower() != "y":
        return
    
    #vault.addStrategy(strategy, deposit_limit, deposit_limit, 500, {"from": dev, 'gas_price':Wei("17 gwei")})

    amount = Wei('0.1 ether')
    amountE = amount.to('ether')
    
    if input(f"approve: {amountE} WETH?").lower() != "y":
        return
    #dai.approve(vault, amount*100, {"from": dev, 'gas_price':Wei("17 gwei")})
    
    print('deposit amount:', amount.to('ether'))
    if input("Continue? y/[N]: ").lower() != "y":
        return
    #vault.deposit(amount, {"from": dev, 'gas_price':Wei("17 gwei")})    

    print('harvest time')
    if input("Continue? y/[N]: ").lower() != "y":
        return
   
    strategy.harvest({"from": dev, 'gas_price':Wei("25 gwei")})