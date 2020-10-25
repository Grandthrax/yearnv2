from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, harvest, assertCollateralRatio
import brownie

def test_deposit_with_fortune(web3, chain, comp, vault, largerunningstrategy, whale, gov, dai, strategist, isolation):

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

    withdraw(1, whale, dai, vault)
    #balance = vault.balanceOf(whale)
    #tx = vault.withdraw(balance, {'from': whale})   
    #print(tx.events['Leverage'])


    profitW = dai.balanceOf(whale) - balanceBefore
    profit = profitW.to('ether')

    print(f'whale lost: {profit:.5f} from huge emergency withdrawal')

    stateOfStrat(largerunningstrategy, dai, comp)
    stateOfVault(vault, largerunningstrategy)

    harvest(largerunningstrategy, gov, vault)
    
    withdraw(1, gov, dai, vault)
    profit = dai.balanceOf(gov)
    profit = profit.to('ether')

    print(f'governance made: {profit:.5f} from shutting down vault')
    stateOfStrat(largerunningstrategy, dai, comp)
    stateOfVault(vault, largerunningstrategy)

    deposit(dai.balanceOf(whale), whale, dai, vault)

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



