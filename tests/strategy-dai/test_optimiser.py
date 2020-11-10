from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, genericStateOfVault,genericStateOfStrat, harvest, tend, assertCollateralRatio
import random
import brownie

def test_setup_deposit(usdc, whale,gov,strategist, Vault, LenderYieldOptimiser, GenericCompound, GenericCream, GenericDyDx, interface):

    #deploy vault
    vault = gov.deploy(
        Vault, usdc, gov, gov, "", ""
    )

    usdc.approve(vault, 2 ** 256 - 1, {"from": whale} )

    #deploy strategy
    strategy = strategist.deploy(LenderYieldOptimiser, vault)

    #cDai = interface.CErc20I('0x5d3a536e4d6dbd6114cc1ead35777bab948e3643')
    cUsdc = interface.CErc20I('0x39AA39c021dfbaE8faC545936693aC917d5E7563')

    assert cUsdc.underlying() == vault.token()
    crUsdc = interface.CErc20I('0x44fbeBd2F576670a6C33f6Fc0B00aA8c5753b322')
    assert crUsdc.underlying() == vault.token()

    compoundPlugin = strategist.deploy(GenericCompound, strategy, "Compound", cUsdc)
    creamPlugin = strategist.deploy(GenericCream, strategy, "Cream", crUsdc)
    dydxPlugin = strategist.deploy(GenericDyDx, strategy, "DyDx")

    strategy.addLender(compoundPlugin, {"from": strategist})
    assert strategy.numLenders() == 1

    strategy.addLender(creamPlugin, {"from": strategist})
    assert strategy.numLenders() == 2

    strategy.addLender(dydxPlugin, {"from": strategist})
    assert strategy.numLenders() == 3

    deposit_limit = 100_000_000 *1e6
    form = "{:.2%}"
    formS = "{:,.0f}"

    vault.addStrategy(strategy, deposit_limit, deposit_limit, 500, {"from": gov})
    for i in range(50):
        firstDeposit = 500_000 *1e6

        print("\nDeposit: ", formS.format(firstDeposit/1e6))
        vault.deposit(firstDeposit, {"from": whale})

        strategy.harvest({"from": strategist})
        status = strategy.lendStatuses()
        
        for j in status:
            print(f"Lender: {j[0]}, Deposits: {formS.format(j[1]/1e6)}, APR: {form.format(j[2]/1e18)}")
        print(f"Total Vault NAV: {formS.format(strategy.estimatedTotalAssets()/1e6)}, Net APR: {form.format(strategy.estimatedAPR()/1e18)}")
    


def test_debt_increase(usdc, whale,gov,strategist, Vault, LenderYieldOptimiser, GenericCompound, GenericCream, GenericDyDx, interface):

    #deploy vault
    vault = gov.deploy(
        Vault, usdc, gov, gov, "", ""
    )

    usdc.approve(vault, 2 ** 256 - 1, {"from": whale} )

    #deploy strategy
    strategy = strategist.deploy(LenderYieldOptimiser, vault)

    #cDai = interface.CErc20I('0x5d3a536e4d6dbd6114cc1ead35777bab948e3643')
    cUsdc = interface.CErc20I('0x39AA39c021dfbaE8faC545936693aC917d5E7563')

    assert cUsdc.underlying() == vault.token()
    crUsdc = interface.CErc20I('0x44fbeBd2F576670a6C33f6Fc0B00aA8c5753b322')
    assert crUsdc.underlying() == vault.token()

    compoundPlugin = strategist.deploy(GenericCompound, strategy, "Compound", cUsdc)
    creamPlugin = strategist.deploy(GenericCream, strategy, "Cream", crUsdc)
    dydxPlugin = strategist.deploy(GenericDyDx, strategy, "DyDx")

    strategy.addLender(compoundPlugin, {"from": strategist})
    assert strategy.numLenders() == 1

    strategy.addLender(creamPlugin, {"from": strategist})
    assert strategy.numLenders() == 2

    strategy.addLender(dydxPlugin, {"from": strategist})
    assert strategy.numLenders() == 3
    
    deposit_limit = 100_000_000 *1e6
    vault.addStrategy(strategy, deposit_limit, deposit_limit, 500, {"from": gov})


    form = "{:.2%}"
    formS = "{:,.0f}"
    firstDeposit = 2000_000 *1e6
    predictedApr = strategy.estimatedFutureAPR(firstDeposit)
    print(f"Predicted APR from {formS.format(firstDeposit/1e6)} deposit: {form.format(predictedApr/1e18)}")
    vault.deposit(firstDeposit, {"from": whale})
    print("Deposit: ", formS.format(firstDeposit/1e6))
    strategy.harvest({"from": strategist})
    realApr = strategy.estimatedAPR()
    print("Current APR: ", form.format(realApr/1e18))
    status = strategy.lendStatuses()
    
    for j in status:
        print(f"Lender: {j[0]}, Deposits: {formS.format(j[1]/1e6)}, APR: {form.format(j[2]/1e18)}")
    
    assert realApr > predictedApr*.999 and realApr <  predictedApr*1.001
    
    predictedApr = strategy.estimatedFutureAPR(firstDeposit*2)
    print(f"\nPredicted APR from {formS.format(firstDeposit/1e6)} deposit: {form.format(predictedApr/1e18)}")
    print("Deposit: ", formS.format(firstDeposit/1e6))
    vault.deposit(firstDeposit, {"from": whale})

    strategy.harvest({"from": strategist})
    realApr = strategy.estimatedAPR()
   
    print(f"Real APR after deposit: {form.format(realApr/1e18)}")
    status = strategy.lendStatuses()
        
    for j in status:
        print(f"Lender: {j[0]}, Deposits: {formS.format(j[1]/1e6)}, APR: {form.format(j[2]/1e18)}")
    assert realApr > predictedApr*.999 and realApr <  predictedApr*1.001

        

def test_optimiser_full_run(usdc, chain, whale,gov,strategist, Vault, LenderYieldOptimiser, GenericCompound, GenericCream, GenericDyDx, interface):
    starting_balance = usdc.balanceOf(strategist)
    currency = usdc
    #deploy vault
    vault = strategist.deploy(
        Vault, usdc, strategist, strategist, "", ""
    )

    usdc.approve(vault, 2 ** 256 - 1, {"from": whale} )
    usdc.approve(vault, 2 ** 256 - 1, {"from": strategist} )

    #deploy strategy
    strategy = strategist.deploy(LenderYieldOptimiser, vault)

    #cDai = interface.CErc20I('0x5d3a536e4d6dbd6114cc1ead35777bab948e3643')
    solo= interface.ISoloMargin('0x1E0447b19BB6EcFdAe1e4AE1694b0C3659614e4e')
    cUsdc = interface.CErc20I('0x39AA39c021dfbaE8faC545936693aC917d5E7563')

    assert cUsdc.underlying() == vault.token()
    crUsdc = interface.CErc20I('0x44fbeBd2F576670a6C33f6Fc0B00aA8c5753b322')
    assert crUsdc.underlying() == vault.token()

    compoundPlugin = strategist.deploy(GenericCompound, strategy, "Compound", cUsdc)
    creamPlugin = strategist.deploy(GenericCream, strategy, "Cream", crUsdc)
    dydxPlugin = strategist.deploy(GenericDyDx, strategy, "DyDx")

    strategy.addLender(compoundPlugin, {"from": strategist})
    assert strategy.numLenders() == 1

    strategy.addLender(creamPlugin, {"from": strategist})
    assert strategy.numLenders() == 2

    strategy.addLender(dydxPlugin, {"from": strategist})
    assert strategy.numLenders() == 3
    
    deposit_limit = 1_000_000_000 *1e6
    vault.addStrategy(strategy, deposit_limit, deposit_limit, 500, {"from": strategist})

    
    #our humble strategist deposits some test funds
    depositAmount =  501 *1e6
    vault.deposit(depositAmount, {"from": strategist})
    #print(vault.creditAvailable(strategy))

    assert strategy.estimatedTotalAssets() == 0
    assert strategy.harvestTrigger(1) == True

    strategy.harvest({"from": strategist})

    assert strategy.estimatedTotalAssets() >= depositAmount*0.999999 #losing some dust is ok
    assert strategy.harvestTrigger(1) == False

    #whale deposits as well
    whale_deposit  =100_000 *1e6
    vault.deposit(whale_deposit, {"from": whale})
    assert strategy.harvestTrigger(1000) == True
    strategy.harvest({"from": strategist})
    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)
    
    form = "{:.2%}"
    formS = "{:,.0f}"

    for i in range(15):
        waitBlock = random.randint(10,50)
        cUsdc.mint(0, {"from": whale})
        crUsdc.mint(0, {"from": whale})
        print(f'\n----wait {waitBlock} blocks----')
        chain.mine(waitBlock)
        chain.sleep(15*30)

        #if harvest condition harvest. if tend tend
        strategy.harvest({"from": strategist})
        something= True
        action = random.randint(0,9)
        if action == 1:
            withdraw(random.randint(50,100),whale, currency, vault)
        elif action == 2:
            withdraw(random.randint(50,100),whale, currency, vault)
        elif action == 3:
            depositAm = random.randint(10,100) *1e6
            print(f'\n----user deposits {depositAm/1e6}----')
            vault.deposit(depositAm, {"from": whale})
        else :
            something = False

        if something:
            genericStateOfStrat(strategy, currency, vault)
            genericStateOfVault(vault, currency)
            status = strategy.lendStatuses()
            for j in status:
                print(f"Lender: {j[0]}, Deposits: {formS.format(j[1]/1e6)}, APR: {form.format(j[2]/1e18)}")

    #strategist withdraws
    withdraw(1, strategist, currency, vault)
    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)

    profit = currency.balanceOf(strategist) - starting_balance

    print(profit/1e6, ' profit')
    print(vault.strategies(strategy)[6] /1e6, ' total returns of strat')


def test_apr_optimser(usdc, chain, whale,gov,strategist, Vault, LenderYieldOptimiser, GenericCompound, GenericCream, GenericDyDx, interface):
    currency = usdc
    solo= interface.ISoloMargin('0x1E0447b19BB6EcFdAe1e4AE1694b0C3659614e4e')
    cUsdc = interface.CErc20I('0x39AA39c021dfbaE8faC545936693aC917d5E7563')
    crUsdc = interface.CErc20I('0x44fbeBd2F576670a6C33f6Fc0B00aA8c5753b322')
    vault = strategist.deploy(
        Vault, usdc, strategist, strategist, "", ""
    )

    usdc.approve(vault, 2 ** 256 - 1, {"from": whale} )
    usdc.approve(vault, 2 ** 256 - 1, {"from": strategist} )

    #deploy strategy
    strategy = strategist.deploy(LenderYieldOptimiser, vault)

    #cDai = interface.CErc20I('0x5d3a536e4d6dbd6114cc1ead35777bab948e3643')
    solo= interface.ISoloMargin('0x1E0447b19BB6EcFdAe1e4AE1694b0C3659614e4e')
    cUsdc = interface.CErc20I('0x39AA39c021dfbaE8faC545936693aC917d5E7563')

    assert cUsdc.underlying() == vault.token()
    crUsdc = interface.CErc20I('0x44fbeBd2F576670a6C33f6Fc0B00aA8c5753b322')
    assert crUsdc.underlying() == vault.token()

    compoundPlugin = strategist.deploy(GenericCompound, strategy, "Compound", cUsdc)
    creamPlugin = strategist.deploy(GenericCream, strategy, "Cream", crUsdc)
    dydxPlugin = strategist.deploy(GenericDyDx, strategy, "DyDx")

    strategy.addLender(compoundPlugin, {"from": strategist})
    assert strategy.numLenders() == 1

    strategy.addLender(creamPlugin, {"from": strategist})
    assert strategy.numLenders() == 2

    strategy.addLender(dydxPlugin, {"from": strategist})
    assert strategy.numLenders() == 3
    
    deposit_limit = 1_000_000_000 *1e6
    vault.addStrategy(strategy, deposit_limit, deposit_limit, 500, {"from": strategist})

    whale_deposit  =100_000 *1e6
    vault.deposit(whale_deposit, {"from": whale})

    harvest(strategy, strategist, vault)

    startingBalance = vault.totalAssets()

    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)

    for i in range(10):
        cUsdc.mint(0, {"from": whale})
        crUsdc.mint(0, {"from": whale})
        waitBlock = 25
        print(f'\n----wait {waitBlock} blocks----')
        chain.mine(waitBlock)
        print(f'\n----harvest----')
        strategy.harvest({'from': strategist})

        genericStateOfStrat(strategy, currency, vault)
        genericStateOfVault(vault, currency)


        profit = (vault.totalAssets() - startingBalance) /1e6
        strState = vault.strategies(strategy)
        totalReturns = strState[6]
        totaleth = totalReturns /1e6
        print(f'Real Profit: {profit:.5f}')
        difff= profit-totaleth
        print(f'Diff: {difff}')

        blocks_per_year = 2_300_000
        assert startingBalance != 0
        time =(i+1)*waitBlock
        assert time != 0
        apr = (totalReturns/startingBalance) * (blocks_per_year / time)
        print(apr)
        print(f'implied apr: {apr:.8%}')

    vault.withdraw(vault.balanceOf(whale), {'from': whale})


def test_good_migration(usdc, chain, whale,gov,strategist,rando,Vault, LenderYieldOptimiser, GenericCompound, GenericCream, GenericDyDx, interface):
    currency = usdc
    solo= interface.ISoloMargin('0x1E0447b19BB6EcFdAe1e4AE1694b0C3659614e4e')
    cUsdc = interface.CErc20I('0x39AA39c021dfbaE8faC545936693aC917d5E7563')
    crUsdc = interface.CErc20I('0x44fbeBd2F576670a6C33f6Fc0B00aA8c5753b322')
    vault = strategist.deploy(
        Vault, usdc, strategist, strategist, "", ""
    )

    usdc.approve(vault, 2 ** 256 - 1, {"from": whale} )
    usdc.approve(vault, 2 ** 256 - 1, {"from": strategist} )

    #deploy strategy
    strategy = strategist.deploy(LenderYieldOptimiser, vault)

    #cDai = interface.CErc20I('0x5d3a536e4d6dbd6114cc1ead35777bab948e3643')
    solo= interface.ISoloMargin('0x1E0447b19BB6EcFdAe1e4AE1694b0C3659614e4e')
    cUsdc = interface.CErc20I('0x39AA39c021dfbaE8faC545936693aC917d5E7563')

    assert cUsdc.underlying() == vault.token()
    crUsdc = interface.CErc20I('0x44fbeBd2F576670a6C33f6Fc0B00aA8c5753b322')
    assert crUsdc.underlying() == vault.token()

    compoundPlugin = strategist.deploy(GenericCompound, strategy, "Compound", cUsdc)
    creamPlugin = strategist.deploy(GenericCream, strategy, "Cream", crUsdc)
    dydxPlugin = strategist.deploy(GenericDyDx, strategy, "DyDx")
    strategy.addLender(compoundPlugin, {"from": strategist})
    assert strategy.numLenders() == 1

    strategy.addLender(creamPlugin, {"from": strategist})
    assert strategy.numLenders() == 2

    strategy.addLender(dydxPlugin, {"from": strategist})
    assert strategy.numLenders() == 3
    
    deposit_limit = 1_000_000_000 *1e6
    vault.addStrategy(strategy, deposit_limit, deposit_limit, 500, {"from": strategist})
    
    amount1 = 500 *1e6
    vault.deposit(amount1, {"from": whale})

    amount1 = 50 *1e6
    vault.deposit(amount1, {"from": strategist})
    gov= strategist

    strategy.harvest({'from': gov})
    wait(30, chain)
    strategy.harvest({'from': gov})

    strategy_debt = vault.strategies(strategy)[4]  # totalDebt
    prior_position = strategy.estimatedTotalAssets()
    assert strategy_debt > 0

    new_strategy = strategist.deploy(LenderYieldOptimiser, vault)
    assert vault.strategies(new_strategy)[4] == 0
    assert currency.balanceOf(new_strategy) == 0

    # Only Governance can migrate
    with brownie.reverts():
        vault.migrateStrategy(strategy, new_strategy, {"from": rando})

    vault.migrateStrategy(strategy, new_strategy, {"from": gov})
    assert vault.strategies(strategy)[4] == 0
    assert vault.strategies(new_strategy)[4] == strategy_debt
    assert new_strategy.estimatedTotalAssets() > prior_position*0.999 or new_strategy.estimatedTotalAssets() < prior_position*1.001