from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, genericStateOfStrat, genericStateOfVault,stateOfVault, deposit,wait, withdraw, harvest, tend, assertCollateralRatio
import random
import brownie


def test_live_status2(web3, chain, live_vault, live_strategy,  comp,dai, samdev):

  