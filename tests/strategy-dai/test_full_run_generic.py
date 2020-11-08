from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, genericStateOfVault,genericStateOfStrat, harvest, tend, assertCollateralRatio
import random
import brownie

def test_full_generic(strategy_changeable, web3, chain, Vault,currency, whale, strategist):
    #our humble strategist is going to publish both the vault and the strategy

    starting_balance = currency.balanceOf(strategist)

    #deploy vault
    vault = strategist.deploy(
        Vault, currency, strategist, strategist, "TestVault", "Amount"
    )

    deposit_limit = Wei('1000000 ether')

    #set limit to the vault
    vault.setDepositLimit(deposit_limit, {"from": strategist})

    #deploy strategy
    strategy = strategist.deploy(strategy_changeable, vault)

    vault.addStrategy(strategy, deposit_limit, deposit_limit, 50, {"from": strategist})

    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)

    
    #our humble strategist deposits some test funds
    depositAmount =  Wei('501 ether')
    deposit(depositAmount, strategist, currency, vault)
    #print(vault.creditAvailable(strategy))
    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)

    assert strategy.estimatedTotalAssets() == 0
    assert strategy.harvestTrigger(1) == True

    harvest(strategy, strategist, vault)

    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)

    assert strategy.estimatedTotalAssets() >= depositAmount*0.999999 #losing some dust is ok
    assert strategy.harvestTrigger(1) == False

    #whale deposits as well
    whale_deposit  = Wei('1000 ether')
    deposit(whale_deposit, whale, currency, vault)
    assert strategy.harvestTrigger(1000000 * 30 * 1e9) == True
    harvest(strategy, strategist, vault)
    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)

    for i in range(15):
        waitBlock = random.randint(10,50)
        print(f'\n----wait {waitBlock} blocks----')
        chain.mine(waitBlock)

        #if harvest condition harvest. if tend tend
        harvest(strategy, strategist, vault)
        tend(strategy, strategist)
        something= True
        action = random.randint(0,9)
        if action == 1:
            withdraw(random.randint(50,100),whale, currency, vault)
        elif action == 2:
            withdraw(random.randint(50,100),whale, currency, vault)
        elif action == 3:
            deposit(Wei(str(f'{random.randint(10,100)} ether')), whale, currency, vault)
        else :
            something = False

        if something:
            genericStateOfStrat(strategy, currency, vault)
            genericStateOfVault(vault, currency)

    #strategist withdraws
    withdraw(1, strategist, currency, vault)
    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)

    profit = currency.balanceOf(strategist) - starting_balance

    print(Wei(profit).to('ether'), ' profit')
    print(vault.strategies(strategy)[6].to('ether'), ' total returns of strat')

