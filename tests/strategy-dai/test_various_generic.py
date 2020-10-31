from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, genericStateOfVault,genericStateOfStrat, harvest, tend, assertCollateralRatio
import random
import brownie

def test_apr_generic(strategy_changeable, web3, chain, Vault,currency, whale, strategist):

    vault = strategist.deploy(
        Vault, currency, strategist, strategist, "TestVault", "Amount"
    )
    deposit_limit = Wei('1000000 ether')
    #set limit to the vault
    vault.setDepositLimit(deposit_limit, {"from": strategist})

    #deploy strategy
    strategy = strategist.deploy(strategy_changeable, vault)

    vault.addStrategy(strategy, deposit_limit, deposit_limit, 50, {"from": strategist})

    deposit_amount = Wei('1000 ether')
    deposit(deposit_amount, whale, currency, vault)

    harvest(strategy, strategist, vault)

    startingBalance = vault.totalAssets()

    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)

    for i in range(50):
        waitBlock = 25
        print(f'\n----wait {waitBlock} blocks----')
        chain.mine(waitBlock)
        print(f'\n----harvest----')
        strategy.harvest({'from': strategist})
        
        genericStateOfStrat(strategy, currency, vault)
        genericStateOfVault(vault, currency)


        profit = (vault.totalAssets() - startingBalance).to('ether')
        strState = vault.strategies(strategy)
        totalReturns = strState[6]
        totaleth = totalReturns.to('ether')
        print(f'Real Profit: {profit:.5f}')
        difff= profit-totaleth
        print(f'Diff: {difff}')

        blocks_per_year = 2_300_000
        assert startingBalance != 0
        time =(i+1)*waitBlock
        assert time != 0
        apr = (totalReturns/startingBalance) * (blocks_per_year / time)
        print(f'implied apr: {apr:.8%}')

    vault.withdraw(vault.balanceOf(whale), {'from': whale})