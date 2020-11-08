from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, genericStateOfVault,genericStateOfStrat, harvest, tend, assertCollateralRatio
import random
import brownie

def test_setup_deposit(usdc, whale,gov,strategist, Vault, LenderYieldOptimiser, GenericCompound, GenericDyDx, interface):

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
    creamPlugin = strategist.deploy(GenericCompound, strategy, "Cream", crUsdc)
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
    





