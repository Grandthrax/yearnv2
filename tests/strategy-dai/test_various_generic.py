from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, genericStateOfVault,genericStateOfStrat, harvest, tend, assertCollateralRatio
import random
import brownie

def test_donations(strategy_changeable, web3, chain, Vault,currency, whale, strategist):
    gov = strategist
    vault = strategist.deploy(
        Vault, currency, strategist, strategist, "TestVault", "Amount"
    )
    deposit_limit = Wei('1000 ether')
    #set limit to the vault
    vault.setDepositLimit(deposit_limit, {"from": strategist})

    #deploy strategy
    strategy = strategist.deploy(strategy_changeable, vault)

    vault.addStrategy(strategy, deposit_limit, deposit_limit, 50, {"from": strategist})
    amount = Wei('500 ether')
    deposit(amount, gov, currency, vault)
    assert vault.strategies(strategy)[5] == 0
    strategy.harvest({'from': gov})
    assert vault.strategies(strategy)[6] == 0 

    donation = Wei('100 ether')

    #donation to strategy
    currency.transfer(strategy, donation, {'from': whale})
    assert vault.strategies(strategy)[6] == 0 
    strategy.harvest({'from': gov})
    assert vault.strategies(strategy)[6] >= donation 
    assert currency.balanceOf(vault) >= donation

    strategy.harvest({'from': gov})
    assert vault.strategies(strategy)[5] >= donation + amount


    #donation to vault
    currency.transfer(vault, donation, {'from': whale})
    assert vault.strategies(strategy)[6] >= donation and  vault.strategies(strategy)[6] < donation*2
    strategy.harvest({'from': gov})
    assert vault.strategies(strategy)[5] >= donation*2 + amount
    strategy.harvest({'from': gov})

    assert vault.strategies(strategy)[6] >= donation and  vault.strategies(strategy)[6] < donation*2
    #check share price is close to expected
    assert vault.pricePerShare() > ((donation*2 + amount)/amount)*0.95*1e18 and  vault.pricePerShare() < ((donation*2 + amount)/amount)*1.05*1e18


def test_good_migration(strategy_changeable, web3, chain, Vault,currency, whale,rando,  strategist):
    # Call this once to seed the strategy with debt
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
    strategy.harvest({'from': gov})

    strategy_debt = vault.strategies(strategy)[4]  # totalDebt
    prior_position = strategy.estimatedTotalAssets()
    assert strategy_debt > 0

    new_strategy = strategist.deploy(strategy_changeable, vault)
    assert vault.strategies(new_strategy)[4] == 0
    assert currency.balanceOf(new_strategy) == 0

    # Only Governance can migrate
    with brownie.reverts():
        vault.migrateStrategy(strategy, new_strategy, {"from": rando})

    vault.migrateStrategy(strategy, new_strategy, {"from": gov})
    assert vault.strategies(strategy)[4] == 0
    assert vault.strategies(new_strategy)[4] == strategy_debt
    assert new_strategy.estimatedTotalAssets() > prior_position*0.999 or new_strategy.estimatedTotalAssets() < prior_position*1.001


def test_vault_shares_generic(strategy_changeable, web3, chain, Vault,currency, whale, strategist):
    gov = strategist
    vault = strategist.deploy(
        Vault, currency, strategist, strategist, "TestVault", "Amount"
    )
    deposit_limit = Wei('1000 ether')
    #set limit to the vault
    vault.setDepositLimit(deposit_limit, {"from": strategist})

    #deploy strategy
    strategy = strategist.deploy(strategy_changeable, vault)

    vault.addStrategy(strategy, deposit_limit, deposit_limit, 50, {"from": strategist})


    amount1 = Wei('50 ether')
    deposit(amount1, whale, currency, vault)
    whale_share = vault.balanceOf(whale)
    deposit(amount1, gov, currency, vault)
    gov_share = vault.balanceOf(gov)

    assert gov_share == whale_share
    assert vault.pricePerShare() == 1e18
    assert vault.pricePerShare()*whale_share/1e18 == amount1
    
    assert vault.pricePerShare()*whale_share/1e18 == vault.totalAssets()/2
    assert gov_share == whale_share

    strategy.harvest({'from': gov})
    #no profit yet
    whale_share = vault.balanceOf(whale)
    gov_share = vault.balanceOf(gov)
    assert gov_share > whale_share

    
    wait(100, chain)
    whale_share = vault.balanceOf(whale)
    gov_share = vault.balanceOf(gov)
    # no profit just aum fee. meaning total balance should be the same
    assert (gov_share + whale_share)*vault.pricePerShare()/ 1e18 == 100*1e18

   
    strategy.harvest({'from': gov})
    whale_share = vault.balanceOf(whale)
    gov_share = vault.balanceOf(gov)
    #add strategy return
    assert vault.totalSupply() == whale_share + gov_share
    value = (gov_share + whale_share)*vault.pricePerShare()/ 1e18
    assert value == 100*1e18 + vault.strategies(strategy)[6]
    #check we are within 0.1% of expected returns
    assert value < strategy.estimatedTotalAssets()*1.001 and value > strategy.estimatedTotalAssets()*0.999
    
    assert gov_share > whale_share



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
    assert currency.balanceOf(strategy) ==0
    strategy.harvest({'from': gov})
    assert currency.balanceOf(strategy) == strategy.estimatedTotalAssets()
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

    for i in range(10):
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
        print(apr)
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
    vault.withdraw(vault.balanceOf(whale), {'from': whale})

    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)






    