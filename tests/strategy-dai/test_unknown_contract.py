from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, harvest,assertCollateralRatio
import brownie
import random

def test_unknown_2(web3,StrategyUniswapPairPickle, Vault, interface, chain,uni_wethwbtc, whaleU, accounts):
    

    starting_balance = uni_wethwbtc.balanceOf(whaleU)
    pjar =  interface.PickleJar('0xc80090aa05374d336875907372ee4ee636cbc562')
    pboss = accounts.at('0xf00d98806a785bb0e1854a0ccc8a39c9c4f4316a', force=True)

    #deploy vault
    vault = whaleU.deploy(
        Vault, uni_wethwbtc, whaleU, whaleU, "ss", "sss"
    )

    strategy = whaleU.deploy(StrategyUniswapPairPickle, vault, pjar, 15)
    deposit_limit = Wei('10 ether')

    vault.addStrategy(strategy, deposit_limit, deposit_limit, 50, {"from": whaleU})

    deposit(Wei('0.0001 ether'), whaleU, uni_wethwbtc, vault)
    strategy.harvest( {'from': whaleU})

    for i in range(20):
        pjar.earn({'from': pboss})
        chain.mine(10)
        withdraw( 10, whaleU, uni_wethwbtc, vault)
        strategy.harvest( {'from': whaleU})
        strState = vault.strategies(strategy)
        totalDebt = strState[5]
        estimateAssets = strategy.estimatedTotalAssets()
        percentd = totalDebt/estimateAssets
        print(f'totalDebt/estimateAssets: {percentd:.5%}')
    
        


def test_unknown_1(web3,StrategyUniswapPairPickle, Vault, chain,uni_wethwbtc, whaleU, accounts):
    
    

  #  vault.withdraw(vault.balanceOf(whale)/2, {'from': whale})

  #  strategy.harvest({'from': gov})

    print('strategy expected returns', strategy.expectedReturn().to('ether'))

    print('vault price per share', vault.pricePerShare())
    print('vault total assets', vault.totalAssets().to('ether'))
    print('strategy total assets:', strategy.estimatedTotalAssets().to('ether'))
    print('Vault total supply', vault.totalSupply().to('ether'))
        
    strState = vault.strategies(strategy)
    stDebtLimit = strState[2].to('ether')
    lastReport = strState[4]
    print(f'last report: {lastReport}')
    print('strategy debt limit ', stDebtLimit)
    totalDebt = strState[5].to('ether')
    rateLimit = strState[3].to('ether')
    totalReturns = strState[6].to('ether')
    print(f'strategy debt: {totalDebt}')
    print(f'rate limit: {rateLimit}')

    print('vault price per share', vault.pricePerShare())
    print('vault total assets', vault.totalAssets().to('ether'))
    print('strategy total assets:', strategy.estimatedTotalAssets().to('ether'))
    print('Vault total supply', vault.totalSupply().to('ether'))
    
    print(f'\n emergency exit \n')
    strategy.setEmergencyExit({'from': gov})
    strState = vault.strategies(strategy)
    stDebtLimit = strState[2].to('ether')
    lastReport = strState[4]
    print(f'last report: {lastReport}')
    print('strategy debt limit ', stDebtLimit)
    totalDebt = strState[5].to('ether')
    rateLimit = strState[3].to('ether')
    totalReturns = strState[6].to('ether')
    print(f'strategy debt: {totalDebt}')
    print(f'rate limit: {rateLimit}')

    print('\nharvest called')
    strategy.harvest({'from': gov})
    #chain.mine(100)

    print('strategy expected returns', strategy.expectedReturn().to('ether'))
    print('vault price per share', vault.pricePerShare())
    print('vault total assets', vault.totalAssets().to('ether'))
    print('strategy total assets:', strategy.estimatedTotalAssets().to('ether'))
    print('Vault total supply', vault.totalSupply().to('ether'))
    strState = vault.strategies(strategy)
    totalDebt = strState[5].to('ether')
    totalReturns = strState[6].to('ether')
    print(f'strategy debt: {totalDebt}')
    print(f'total returns: {totalReturns}')

    
    for i in range(15):
        #assertCollateralRatio(strategy)
        waitBlock = random.randint(0,3)
        print(f'\n----wait {waitBlock} blocks----')
        chain.mine(waitBlock)

        
        #if harvest condition harvest. if tend tend

        something= True
        action = random.randint(0,9)
        if action == 1:
            vault.withdraw(vault.balanceOf(whale)*.999, {'from': whale})
        elif action == 2:
            vault.withdraw(vault.balanceOf(whale)*.999, {'from': whale})
        #elif action == 3:
            #deposit(Wei(str(f'{random.randint(10000,100000)} ether')), whale, dai, vault)
        elif action >3 and action < 6:
            strategy.harvest({'from': gov})
        else :
            something = False

        if something:
            print('\nstrategy expected returns', strategy.expectedReturn().to('ether'))
            print('vault price per share', vault.pricePerShare())
            print('vault total assets', vault.totalAssets().to('ether'))
            print('strategy total assets:', strategy.estimatedTotalAssets().to('ether'))
            print('Vault total supply', vault.totalSupply().to('ether'))
            strState = vault.strategies(strategy)
            totalDebt = strState[5].to('ether')
            totalReturns = strState[6].to('ether')
            print(f'strategy debt: {totalDebt}')
            print(f'total returns: {totalReturns}')
