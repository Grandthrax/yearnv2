from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, harvest, tend, assertCollateralRatio
import random
import brownie

def test_full_live(web3, chain, comp, live_strategy, live_vault, samdev, dai,cdai):
    stateOfStrat(live_strategy, dai, comp)
    stateOfVault(live_vault, live_strategy)

  #  #live_vault.setEmergencyShutdown(True, {"from": samdev})

 #   #live_strategy.harvest({'from': samdev})

#    live_vault.withdraw(live_vault.balanceOf(samdev), {'from': samdev})

