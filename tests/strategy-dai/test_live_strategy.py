from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, harvest, tend, assertCollateralRatio
import random
import brownie

def test_live_status(web3,  live_vault, live_strategy,  comp,dai, samdev):
  stateOfStrat(live_strategy, dai, comp)
  stateOfVault(live_vault, live_strategy)


def migration_live(web3,  comp, YearnDaiCompStratV2,live_strategy, live_vault,  dai, samdev):
    #stateOfStrat(live_strategy, dai, comp)
   # stateOfVault(live_vault, live_strategy)
    old_strategy = YearnDaiCompStratV2.at('0x4C6e9d7E5d69429100Fcc8afB25Ea980065e2773')

    live_strategy = YearnDaiCompStratV2.at('0x5b62F24581Ea4bc6d6C5C101DD2Ae7233E422884')

    print(f'strategy YearnDaiCompStratV2: {live_strategy.address}')

    print(f'Vault: {live_vault.address}')
    print(f'Vault name: {live_vault.name()} and symbol: {live_vault.symbol()}')

    print(f'Strategy strategist: {live_strategy.strategist()}')

    stateOfStrat(old_strategy, dai, comp)
    stateOfVault(live_vault, old_strategy)

    stateOfStrat(live_strategy, dai, comp)
    stateOfVault(live_vault, live_strategy)

    print(f'Migrating')
    live_vault.migrateStrategy(old_strategy, live_strategy, {'from': samdev})

    stateOfStrat(old_strategy, dai, comp)
    stateOfVault(live_vault, old_strategy)

    stateOfStrat(live_strategy, dai, comp)
    stateOfVault(live_vault, live_strategy)

    print(f'Harvesting')
    live_strategy.harvest({'from': samdev})

    stateOfStrat(live_strategy, dai, comp)
    stateOfVault(live_vault, live_strategy)



  #  #live_vault.setEmergencyShutdown(True, {"from": samdev})

 #   #live_strategy.harvest({'from': samdev})

#    live_vault.withdraw(live_vault.balanceOf(samdev), {'from': samdev})

