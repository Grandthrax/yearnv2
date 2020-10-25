from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, harvest,assertCollateralRatio
import brownie

def test_getting_too_close_to_liq(web3, chain, comp, vault, largerunningstrategy, whale, gov, dai):

    stateOfStrat(largerunningstrategy, dai, comp)
    stateOfVault(vault, largerunningstrategy)
    largerunningstrategy.setCollateralTarget(Wei('0.74999999999 ether'), {"from": gov} )
    deposit(Wei('1000 ether'), whale, dai, vault)

    balanceBefore = vault.totalAssets()
    collat = 0

    while collat < largerunningstrategy.collateralTarget() / 1.001e18:

        largerunningstrategy.harvest({'from': gov})
        deposits, borrows = largerunningstrategy.getCurrentPosition()
        collat = borrows / deposits

        stateOfStrat(largerunningstrategy, dai, comp)
        stateOfVault(vault, largerunningstrategy)
        assertCollateralRatio(largerunningstrategy)

    print(largerunningstrategy.getblocksUntilLiquidation())
    print(largerunningstrategy.tendTrigger(0))
    largerunningstrategy.tend({'from': gov})
    assertCollateralRatio(largerunningstrategy)
    stateOfStrat(largerunningstrategy, dai, comp)
    stateOfVault(vault, largerunningstrategy)

    largerunningstrategy.setCollateralTarget(Wei('0.73 ether'), {"from": gov} )
    print(largerunningstrategy.tendTrigger(0))
    largerunningstrategy.tend({'from': gov})
    assertCollateralRatio(largerunningstrategy)
    stateOfStrat(largerunningstrategy, dai, comp)
    stateOfVault(vault, largerunningstrategy)

def test_profit_is_registered(web3, chain, comp, vault, largerunningstrategy, whale, gov, dai):

    stateOfStrat(largerunningstrategy, dai)
    stateOfVault(vault, largerunningstrategy)
    #1m deposit
    amount = Wei('1000000 ether')
    deposit(amount, whale, dai, vault)
    harvest(largerunningstrategy, gov)

    #all money in vault
    assert largerunningstrategy.estimatedTotalAssets() > amount*0.99
    stateOfStrat(largerunningstrategy, dai)
    stateOfVault(vault, largerunningstrategy)

    sample = 500

    wait(sample, chain)
    harvest(largerunningstrategy, gov)
    stateOfStrat(largerunningstrategy, dai)
    stateOfVault(vault, largerunningstrategy)

    debt = vault.strategies(largerunningstrategy)[5]
    returns = vault.strategies(largerunningstrategy)[6]
    assert returns > 0

    blocks_per_year = 2_300_000
    apr = returns/debt * (blocks_per_year / sample)
    print(f'implied apr: {apr:.8%}')

    assert apr > 0
