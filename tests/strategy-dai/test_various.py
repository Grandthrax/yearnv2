from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, harvest,assertCollateralRatio
import brownie

def test_emergency_exit(web3,strategy, vault, chain, dai,cdai, gov, comp):
    amount1 = Wei('500 ether')
    deposit(amount1, gov, dai, vault)

    strategy.harvest({'from': gov})
    wait(30, chain)

    assert vault.emergencyShutdown() == False

    vault.setEmergencyShutdown(True, {"from": gov})
    assert vault.emergencyShutdown()

    stateOfStrat(strategy, dai, comp)
    stateOfVault(vault, strategy)
    strategy.harvest({'from': gov})
    print('\n Emergency shut down + harvest done')
    stateOfStrat(strategy, dai, comp)
    stateOfVault(vault, strategy)

    print('\n Withdraw All')
    vault.withdraw(vault.balanceOf(gov), {'from': gov})

    stateOfStrat(strategy, dai, comp)
    stateOfVault(vault, strategy)

    

def test_sweep(web3,strategy, dai,cdai, gov, comp):
    with brownie.reverts("!protected"):
        strategy.sweep(dai, {"from": gov})

    with brownie.reverts("!protected"):
        strategy.sweep(comp, {"from": gov})

    with brownie.reverts("!protected"):
        strategy.sweep(cdai, {"from": gov})

    cbat = "0x6c8c6b02e7b2be14d4fa6022dfd6d75921d90e4e"

    strategy.sweep(cbat, {"from": gov})

    

def test_apr(web3, chain, comp, vault, enormousrunningstrategy, whale, gov, dai, strategist):
    enormousrunningstrategy.setGasFactor(1, {"from": strategist} )
    assert(enormousrunningstrategy.gasFactor() == 1)

    startingBalance = vault.totalAssets()

    stateOfStrat(enormousrunningstrategy, dai, comp)
    stateOfVault(vault, enormousrunningstrategy)

    for i in range(50):
        assert vault.creditAvailable(enormousrunningstrategy) == 0
        waitBlock = 25
        print(f'\n----wait {waitBlock} blocks----')
        chain.mine(waitBlock)
        
        harvest(enormousrunningstrategy, strategist, vault)
        stateOfStrat(enormousrunningstrategy, dai, comp)
        stateOfVault(vault, enormousrunningstrategy)

        profit = (vault.totalAssets() - startingBalance).to('ether')
        strState = vault.strategies(enormousrunningstrategy)
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
        print(f'implied apr: {apr:.8%}')
    vault.withdraw(vault.balanceOf(whale), {'from': whale})


def test_profit_is_expected(web3, chain, comp, vault, enormousrunningstrategy, whale, gov, dai, strategist):
    enormousrunningstrategy.setGasFactor(1, {"from": strategist} )
    assert(enormousrunningstrategy.gasFactor() == 1)

    startingBalance = vault.totalAssets()

    stateOfStrat(enormousrunningstrategy, dai, comp)
    stateOfVault(vault, enormousrunningstrategy)

    for i in range(50):
        assert vault.creditAvailable(enormousrunningstrategy) == 0
        waitBlock = 25
        print(f'\n----wait {waitBlock} blocks----')
        chain.mine(waitBlock)
        
        harvest(enormousrunningstrategy, strategist, vault)
        stateOfStrat(enormousrunningstrategy, dai, comp)
        stateOfVault(vault, enormousrunningstrategy)

        profit = (vault.totalAssets() - startingBalance).to('ether')
        strState = vault.strategies(enormousrunningstrategy)
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
        print(f'implied apr: {apr:.8%}')
    vault.withdraw(vault.balanceOf(whale), {'from': whale})




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

    stateOfStrat(largerunningstrategy, dai, comp)
    stateOfVault(vault, largerunningstrategy)
    #1m deposit
    amount = Wei('1000000 ether')
    deposit(amount, whale, dai, vault)
    harvest(largerunningstrategy, gov)

    #all money in vault
    assert largerunningstrategy.estimatedTotalAssets() > amount*0.99
    stateOfStrat(largerunningstrategy, dai, comp)
    stateOfVault(vault, largerunningstrategy)

    sample = 500

    wait(sample, chain)
    harvest(largerunningstrategy, gov)
    stateOfStrat(largerunningstrategy, dai, comp)
    stateOfVault(vault, largerunningstrategy)

    debt = vault.strategies(largerunningstrategy)[5]
    returns = vault.strategies(largerunningstrategy)[6]
    assert returns > 0

    blocks_per_year = 2_300_000
    apr = returns/debt * (blocks_per_year / sample)
    print(f'implied apr: {apr:.8%}')

    assert apr > 0
