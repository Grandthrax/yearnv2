from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, harvest
import brownie

def test_gas(web3, chain, comp, vault, YearnDaiCompStratV2, dai, gov):

    