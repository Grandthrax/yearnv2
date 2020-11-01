from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, genericStateOfVault,genericStateOfStrat, harvest, tend, assertCollateralRatio
import random
import brownie

def test_liquidity_crunch(YearnWethCreamStratV2, web3, chain, Vault,Contract, currency, whale, strategist):
    #how much creth does whale have?
    crEth = Contract.from_explorer('0xD06527D5e56A3495252A528C4987003b712860eE')
    balance = crEth.balanceOf(whale)* crEth.exchangeRateStored() /1e18
    print('balance of whale ', balance/1e18)
    


    gov = strategist
    vault = strategist.deploy(
        Vault, currency, strategist, strategist, "TestVault", "Amount"
    )
    deposit_limit = Wei('10000 ether')
    #set limit to the vault
    vault.setDepositLimit(deposit_limit, {"from": strategist})

    #deploy strategy
    strategy = strategist.deploy(YearnWethCreamStratV2, vault)

    vault.addStrategy(strategy, deposit_limit, deposit_limit, 50, {"from": strategist})
    amount = Wei('300 ether')
    print('liquidity before', crEth.getCash()/1e18)
    deposit(amount, gov, currency, vault)
    strategy.harvest({'from': gov})

    liquidity = crEth.getCash()
    print('liquidity ', liquidity/1e18)

    
    
    #get just above liquidity
    newCushion = liquidity - 1
    strategy.setLiquidityCushion(newCushion, {"from": strategist})
    print('new cushion ', newCushion/1e18)
    assert strategy.liquidityCushion() == newCushion

    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)

    assert strategy.tendTrigger(1000000 * 30 * 1e9) == False
    assert strategy.harvestTrigger(1000000 * 30 * 1e9) == False

    #redeem enough to require a change
    crEth.redeemUnderlying(Wei('100 ether'), {'from':whale})
    
    liquidity = crEth.getCash()
    print('new liquidity ', liquidity/1e18)
    print('new cushion ', strategy.liquidityCushion()/1e18)

    assert strategy.tendTrigger(1000000 * 30 * 1e9) == True
    assert strategy.harvestTrigger(1000000 * 30 * 1e9) == False
    
    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)

    strategy.tend({'from': gov})
    
    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)
    assert newCushion - liquidity < currency.balanceOf(strategy)*1.0001 and newCushion - liquidity > currency.balanceOf(strategy)*0.9999
    tokeep = strategy.liquidityCushion() - crEth.getCash()
    print("to keep: ", tokeep/1e18)
    assert strategy.tendTrigger(1000000 * 30 * 1e9) == False
    assert strategy.harvestTrigger(1000000 * 30 * 1e9) == False

    crEth.redeemUnderlying(Wei('500 ether'), {'from':whale})

    assert strategy.tendTrigger(1000000 * 30 * 1e9) == True
    assert strategy.harvestTrigger(1000000 * 30 * 1e9) == False
    strategy.tend({'from': gov})
    assert strategy.tendTrigger(1000000 * 30 * 1e9) == False
    assert strategy.harvestTrigger(1000000 * 30 * 1e9) == False
    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)
    print(crEth.balanceOf(strategy))
    #leave 1 for rounding
    assert crEth.balanceOf(strategy) == 1

    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)

    newCushion = 1
    strategy.setLiquidityCushion(newCushion, {"from": strategist})
    assert strategy.tendTrigger(1000000 * 30 * 1e9) == True
    assert strategy.harvestTrigger(1000000 * 30 * 1e9) == False
    strategy.tend({'from': gov})
    assert strategy.tendTrigger(1000000 * 30 * 1e9) == False
    assert strategy.harvestTrigger(1000000 * 30 * 1e9) == False
    assert currency.balanceOf(strategy) == 0
    assert vault.strategies(strategy)[6] < Wei('1 ether') 

    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)
