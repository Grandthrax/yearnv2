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

    sample = 500

    wait(sample, chain)
    harvest(largerunningstrategy, gov)
    stateOfStrat(largerunningstrategy, dai)
    stateOfVault(vault, largerunningstrategy)

    debt = vault.strategies(largerunningstrategy)[5]
    returns = vault.strategies(largerunningstrategy)[6]
    assert returns > 0

    blocks_per_year = 2_300_000
    apr = returns/debt * (blocks_per_year / sample)
    print(f'implied apr: {apr:.8%}')

    assert apr > 0
