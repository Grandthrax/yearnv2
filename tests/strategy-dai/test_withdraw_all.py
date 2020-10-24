from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, harvest
import brownie

def test_withdraw_all(web3, chain, comp, vault, largerunningstrategy, whale, gov, dai, strategist):

    balance_before = dai.balanceOf(strategist)
    stateOfStrat(largerunningstrategy, dai)
    stateOfVault(vault, largerunningstrategy)

    
    amount = Wei('10000 ether')
    deposit(amount, strategist, dai, vault)
    harvest(largerunningstrategy, gov)

    wait(1000, chain)
    harvest(largerunningstrategy, gov)
    stateOfStrat(largerunningstrategy, dai)
    stateOfVault(vault, largerunningstrategy)

    withdraw(1,strategist, dai, vault)

    profitW = dai.balanceOf(strategist) - balance_before
    profit = profitW.to('ether')
    print(f'profit: {profit:.5%}')