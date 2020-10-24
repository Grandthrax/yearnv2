from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, harvest, tend, assertCollateralRatio
import random
import brownie

def test_full_live(web3, chain, comp, Vault,YearnDaiCompStratV2, dai, whale, strategist,cdai):
    #our humble strategist is going to publish both the vault and the strategy

    # this is to mint small amount of dai reguarly to replicate people interacting with cdai contract
    dai.approve(cdai, 2 ** 256 - 1, {"from": whale})

    starting_balance = dai.balanceOf(strategist)

    #deploy vault
    vault = strategist.deploy(
        Vault, dai, strategist, strategist, "Ytest DAI Vault V2", "ytDAI2"
    )

    #100k dai limit to begin with
    deposit_limit = Wei('1000000 ether')

    #set limit to the vault
    vault.setDepositLimit(deposit_limit, {"from": strategist})

    #deploy strategy
    strategy = strategist.deploy(YearnDaiCompStratV2, vault)

    #enable the strategy
    rate_limit = deposit_limit
    vault.addStrategy(strategy, deposit_limit, rate_limit, 50, {"from": strategist})

    #our humble strategist deposits some test funds
    deposit( Wei('1000 ether'), strategist, dai, vault)
    stateOfStrat(strategy, dai)
    stateOfVault(vault, strategy)
    assert strategy.estimatedTotalAssets() == 0

    harvest(strategy, strategist)

    #whale deposits as well
    deposit( Wei('1000 ether'), whale, dai, vault)

    for i in range(100):
        assertCollateralRatio(strategy)
        waitBlock = random.randint(1,20)
        print(f'\n----wait {waitBlock} blocks----')
        chain.mine(waitBlock)

        #if harvest condition harvest. if tend tend
        harvest(strategy, strategist)
        tend(strategy, strategist)
        something= True
        action = random.randint(0,9)
        if action == 1:
            withdraw(random.randint(2,100),whale, dai, vault)
        elif action == 2:
            withdraw(random.randint(2,100),whale, dai, vault)
        elif action == 3:
            deposit(Wei(str(f'{random.randint(100,100000)} ether')), whale, dai, vault)
        elif action >3 and action < 6:
            cdai.mint(1, {"from": whale})
        else :
            something = False

        if something:
            stateOfStrat(strategy, dai)
            stateOfVault(vault, strategy)

    #strategist withdraws
    withdraw(1, strategist, dai, vault)
    stateOfStrat(strategy, dai)
    stateOfVault(vault, strategy)

    profit = dai.balanceOf(strategist) - starting_balance


    print(Wei(profit).to('ether'), ' profit')
    print(vault.strategies(strategy).totalReturns, ' total returns of strat')

