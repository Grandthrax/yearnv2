from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, harvest
import brownie

def test_profit_is_registered(web3, chain, comp, vault, largerunningstrategy, whale, gov, dai):

    stateOfStrat(largerunningstrategy, dai)
    stateOfVault(vault, largerunningstrategy)
    #1m deposit
    amount = Wei('1000000 ether')
    deposit(amount, whale, dai, vault)
    harvest(largerunningstrategy, gov)

    #all money in vault
    assert largerunningstrategy.estimatedTotalAssets() > amount*0.99
    stateOfStrat(largerunningstrategy, dai)
    stateOfVault(vault, largerunningstrategy)

    sample = 1000

    wait(1000, chain)
    harvest(largerunningstrategy, gov)
    stateOfStrat(largerunningstrategy, dai)
    stateOfVault(vault, largerunningstrategy)

    debt = vault.strategies(strategy)[5]
    returns = vault.strategies(strategy)[6]
    assert returns > 0

    blocks_per_year = 2_300_000
    apr = returns/debt * (blocks_per_year / sample)
    print(f'implied apr: {apr:.8%}')

    assert apr > 0


def test_withdraw_all(web3, chain, comp, vault, largerunningstrategy, whale, gov, dai, strategist):

    balance_before = dai.balanceOf(strategist)
    stateOfStrat(largerunningstrategy, dai)
    stateOfVault(vault, largerunningstrategy)

    
    amount = Wei('10000 ether')
    deposit(amount, strategist, dai, vault)
    harvest(largerunningstrategy, gov)

    wait(1000, chain)
    harvest(largerunningstrategy, gov)
    stateOfStrat(largerunningstrategy, dai)
    stateOfVault(vault, largerunningstrategy)

    withdraw(1,strategist, dai, vault)

    profitW = dai.balanceOf(strategist) - balance_before
    profit = profitW.to('ether')
    print(f'profit: {profit:.5%}')

