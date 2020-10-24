from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, harvest
import brownie

def test_comp_dis(web3, chain, comp, vault, largerunningstrategy, dai, gov):

    stateOfStrat(largerunningstrategy, dai)
    stateOfVault(vault, largerunningstrategy)

    wait(100, chain)

    # Claim COMP and check balance in strategy -> for testing _claimComp() needs to be public
    print('\n----checking comp----')
    balanceBefore = comp.balanceOf(largerunningstrategy)
    
    comp_prediction = largerunningstrategy._predictCompAccrued()
    print(comp_prediction.to('ether'), 'comp accrued')
    largerunningstrategy._claimComp({'from': gov})
    comp_balance = comp.balanceOf(largerunningstrategy) -balanceBefore
    print(comp_balance.to('ether'), 'comp claimed')

    assert comp_balance< comp_prediction*1.1 and comp_balance> comp_prediction*0.9

    stateOfStrat(largerunningstrategy, dai)
    stateOfVault(vault, largerunningstrategy)
