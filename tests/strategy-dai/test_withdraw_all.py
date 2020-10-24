from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, harvest, assertCollateralRatio
import brownie

def test_deposit_with_fortune(web3, chain, comp, vault, largerunningstrategy, whale, gov, dai, strategist, fn_isolation):

    stateOfStrat(largerunningstrategy, dai)
    stateOfVault(vault, largerunningstrategy)

    deposit(dai.balanceOf(whale), whale, dai, vault)
    collat = 0

    while collat < largerunningstrategy.collateralTarget() / 1.001e18:
        largerunningstrategy.harvest({'from': gov})
        deposits, borrows = largerunningstrategy.getCurrentPosition()
        collat = borrows / deposits
        print(collat)

        stateOfStrat(largerunningstrategy, dai)
        stateOfVault(vault, largerunningstrategy)
        assertCollateralRatio(largerunningstrategy)

    harvest(largerunningstrategy, gov)
    stateOfStrat(largerunningstrategy, dai)
    stateOfVault(vault, largerunningstrategy)

    withdraw(1,whale, dai, vault)

def test_withdraw_all(web3, chain, comp, vault, largerunningstrategy, whale, gov, dai, strategist, fn_isolation):

    balance_before = dai.balanceOf(strategist)
    stateOfStrat(largerunningstrategy, dai)
    stateOfVault(vault, largerunningstrategy)

    
    amount = Wei('10000 ether')
    deposit(amount, strategist, dai, vault)
    harvest(largerunningstrategy, gov)

    wait(50, chain)
    harvest(largerunningstrategy, gov)
    stateOfStrat(largerunningstrategy, dai)
    stateOfVault(vault, largerunningstrategy)

    withdraw(1,strategist, dai, vault)

    profitW = dai.balanceOf(strategist) - balance_before
    profit = profitW.to('ether')
    print(f'profit: {profit:.5f}')


