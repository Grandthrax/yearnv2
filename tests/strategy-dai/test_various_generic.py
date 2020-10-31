from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, genericStateOfVault,genericStateOfStrat, harvest, tend, assertCollateralRatio
import random
import brownie

def test_emergency_exit_generic(strategy_changeable, web3, chain, Vault,currency, whale, strategist):
    gov = strategist
    vault = strategist.deploy(
        Vault, currency, strategist, strategist, "TestVault", "Amount"
    )
    deposit_limit = Wei('1000000 ether')
    #set limit to the vault
    vault.setDepositLimit(deposit_limit, {"from": strategist})

    #deploy strategy
    strategy = strategist.deploy(strategy_changeable, vault)

    vault.addStrategy(strategy, deposit_limit, deposit_limit, 50, {"from": strategist})


    amount1 = Wei('500 ether')
    deposit(amount1, whale, currency, vault)

    amount1 = Wei('50 ether')
    deposit(amount1, gov, currency, vault)

    strategy.harvest({'from': gov})
    wait(30, chain)

    assert vault.emergencyShutdown() == False

    vault.setEmergencyShutdown(True, {"from": gov})
    assert vault.emergencyShutdown()

    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)
    strategy.harvest({'from': gov})
    strategy.harvest({'from': gov})
    print('\n Emergency shut down + harvest done')
    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)

    print('\n Withdraw All')
    vault.withdraw(vault.balanceOf(gov), {'from': gov})

    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)

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

    for i in range(5):
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

def test_emergency_exit_generic(strategy_changeable, web3, chain, Vault,currency, whale, strategist):
    gov = strategist
    vault = strategist.deploy(
        Vault, currency, strategist, strategist, "TestVault", "Amount"
    )
    deposit_limit = Wei('1000000 ether')
    #set limit to the vault
    vault.setDepositLimit(deposit_limit, {"from": strategist})

    #deploy strategy
    strategy = strategist.deploy(strategy_changeable, vault)

    vault.addStrategy(strategy, deposit_limit, deposit_limit, 50, {"from": strategist})


    amount1 = Wei('500 ether')
    deposit(amount1, whale, currency, vault)

    amount1 = Wei('50 ether')
    deposit(amount1, gov, currency, vault)

    strategy.harvest({'from': gov})
    wait(30, chain)

    assert vault.emergencyShutdown() == False

    vault.setEmergencyShutdown(True, {"from": gov})
    assert vault.emergencyShutdown()

    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)
    strategy.harvest({'from': gov})
    print('\n Emergency shut down + harvest done')
    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)

    print('\n Withdraw All')
    vault.withdraw(vault.balanceOf(gov), {'from': gov})

    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)