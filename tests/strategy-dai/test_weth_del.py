from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, genericStateOfStrat, genericStateOfVault,stateOfVault, deposit,wait, withdraw, harvest, tend, assertCollateralRatio
import random
import brownie


def test_weth_del(web3, chain, Vault, StrategyMKRVaultDAIDelegate, live_vault, live_strategy, whale, comp,dai,weth, samdev):

    #deploy new strat
    weth_vault = samdev.deploy(
        Vault, weth, samdev, samdev, "", ""
    )

    strategy = samdev.deploy(StrategyMKRVaultDAIDelegate, weth_vault)

    weth_vault.addStrategy(strategy, 2 ** 256 - 1, 2 ** 256 - 1, 50, {"from": samdev})

    deposit( Wei('100 ether'), whale,weth, weth_vault)

    #print("\n******* Dai ******")
    #genericStateOfStrat(live_strategy, dai, live_vault)
    #genericStateOfVault(live_vault, dai)

    #print("\n******* Weth ******")
    #genericStateOfStrat(strategy, weth, weth_vault)
    #genericStateOfVault(weth_vault, weth)

    print("\n******* Harvest Weth ******")
    strategy.harvest({'from': samdev})

    print("\n******* Weth ******")
    genericStateOfStrat(strategy, weth, weth_vault)
    genericStateOfVault(weth_vault, weth)
    print("\n******* Dai ******")
    genericStateOfStrat(live_strategy, dai, live_vault)
    genericStateOfVault(live_vault, dai)




    print("\n******* Harvest Dai ******")
    live_strategy.harvest({'from': samdev})

    print("\n******* Weth ******")
    genericStateOfStrat(strategy, weth, weth_vault)
    genericStateOfVault(weth_vault, weth)
    print("\n******* Dai ******")
    genericStateOfStrat(live_strategy, dai, live_vault)
    genericStateOfVault(live_vault, dai)

  