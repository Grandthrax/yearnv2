from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, harvest, assertCollateralRatio
import brownie


def test_leverage_up_and_down(web3, chain, comp, vault, largerunningstrategy, whale, gov, dai, strategist, isolation):

    stateOfStrat(largerunningstrategy, dai, comp)
    stateOfVault(vault, largerunningstrategy)

    deposit(dai.balanceOf(whale), whale, dai, vault)

    balanceBefore = vault.totalAssets()
    collat = 0

    while collat < largerunningstrategy.collateralTarget() / 1.001e18:
   # while collat < largerunningstrategy.collateralTarget() :

        largerunningstrategy.harvest({'from': gov})
        deposits, borrows = largerunningstrategy.getCurrentPosition()
        collat = borrows / deposits
        print(collat)

        stateOfStrat(largerunningstrategy, dai, comp)
        stateOfVault(vault, largerunningstrategy)
        assertCollateralRatio(largerunningstrategy)

    harvest(largerunningstrategy, gov, vault)
    stateOfStrat(largerunningstrategy, dai, comp)
    stateOfVault(vault, largerunningstrategy)

    largerunningstrategy.setCollateralTarget(Wei('0.1 ether'), {"from": gov} )
    largerunningstrategy.tend({'from': gov})

    stateOfStrat(largerunningstrategy, dai, comp)
    stateOfVault(vault, largerunningstrategy)

    while collat > largerunningstrategy.collateralTarget() / 1e18:
   # while collat < largerunningstrategy.collateralTarget() :

        largerunningstrategy.tend({'from': gov})
        deposits, borrows = largerunningstrategy.getCurrentPosition()
        collat = borrows / deposits
        print(collat)

        stateOfStrat(largerunningstrategy, dai, comp)
        stateOfVault(vault, largerunningstrategy)



def test_withdraw_all(web3, chain, comp, vault, largerunningstrategy, whale, gov, dai, strategist, isolation):

    balance_before = dai.balanceOf(strategist)
    stateOfStrat(largerunningstrategy, dai, comp)
    stateOfVault(vault, largerunningstrategy)

    
    amount = Wei('10000 ether')
    deposit(amount, strategist, dai, vault)
    harvest(largerunningstrategy, gov, vault)

    wait(50, chain)
    harvest(largerunningstrategy, gov, vault)
    stateOfStrat(largerunningstrategy, dai, comp)
    stateOfVault(vault, largerunningstrategy)

    withdraw(1,strategist, dai, vault)


    profitW = dai.balanceOf(strategist) - balance_before
    profit = profitW.to('ether')
    print(f'profit: {profit:.5f}')



