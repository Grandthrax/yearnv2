from itertools import count
from brownie import Wei, reverts
import brownie


def initialMigrate(strategy,vault, whale, ychad, dai, controller):
    print('\n----migrating strategy----')
    controller.approveStrategy(dai, strategy, {'from': ychad})
    controller.setStrategy(dai, strategy, {'from': ychad})
    vault.setMin(10000, {'from': ychad})
    assert controller.strategies(dai) == strategy
    daiInVault = dai.balanceOf(vault)
    earn(strategy, vault, ychad)
    deposit('10000 ether', whale, dai, vault)
    earn(strategy, vault, ychad)

    assert(dai.balanceOf(vault) == 0, "All money should now be in strat")
    assert(dai.balanceOf(strategy) == 0, "All money in strat should be invested")
  
    deposits, borrows = strategy.getCurrentPosition()
    assert(borrows > 0, "Should have borrowed some")
    assert(deposits > 0, "Should have lent some")

def harvest(strategy, keeper):
    print('\n----bot calls harvest----')
    assert strategy.harvestTrigger(0)
    harvestCondition = strategy.harvestTrigger(0, {'from': keeper})

    if harvestCondition:
        strategy.harvest({'from': keeper})

def earn(strategy, vault, user):
    print('\n----bot calls earn----')
    vault.earn({'from': user})
    stateOf(strategy)

def stateOfStrat(strategy, dai):
    print('\n----state of strat----')
    deposits, borrows = strategy.getCurrentPosition()
    print('DAI:',dai.balanceOf(strategy).to('ether'))
    print('borrows:', Wei(borrows).to('ether'))  
    print('deposits:', Wei(deposits).to('ether'))
    print('borrows:', Wei(borrows).to('ether'))  
    print('total assets:', strategy.estimatedTotalAssets().to('ether'))  
    if deposits == 0:
        collat = 0 
    else:
        collat = borrows / deposits
    leverage = 1 / (1 - collat)
    print(f'collat: {collat:.5%}')
    print(f'leverage: {leverage:.5f}x')
    
    assert( collat < strategy.collateralTarget(), "Over collateral target!")
    print('Expected Profit:', strategy.expectedReturn().to('ether'))

def stateOfVault(vault, strategy):
    print('\n----state of vault----')
    strState = vault.strategies(strategy)
    print(strState)
    balance = vault.totalAssets().to('ether')
    print(f'Total Assets: {balance:.5f}x')

def wait(time, chain):
    print(f'\nWaiting {time} blocks')
    chain.mine(time)

def deposit(amount, user, dai, vault):
    print('\n----user deposits----')
    dai.approve(vault, amount, {'from': user})
    print('deposit amount:', amount.to('ether'))
    vault.deposit(amount, {'from': user})    

def withdraw(share, strategy,whale, dai, vault):
   
    print(f'\n----user withdraws {share} shares----')
    balanceBefore = dai.balanceOf(whale)
    vault.withdraw(vault.balanceOf(whale)*share, {'from': whale})
    balanceAfter = dai.balanceOf(whale)
    moneyOut = balanceAfter-balanceBefore
    print('Money Out:', Wei(moneyOut).to('ether'))