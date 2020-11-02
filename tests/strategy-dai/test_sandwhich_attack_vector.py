from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, genericStateOfVault,genericStateOfStrat, harvest, tend, assertCollateralRatio
import random
import brownie

def test_sandwhich_attack_vector(TestHighYieldStrategy, web3, accounts, chain, Vault,Contract, currency, whale, strategist):

   
    crEth = Contract.from_explorer('0xD06527D5e56A3495252A528C4987003b712860eE')
    comptroller = Contract.from_explorer('0x3d5BC3c8d13dcB8bF317092d84783c2697AE9258')
    crSushi = Contract.from_explorer('0x338286C0BC081891A4Bda39C7667ae150bf5D206')
    sushi = Contract.from_explorer('0x6b3595068778dd592e39a122f4f5a5cf09c90fe2')

    honest_lp = accounts.at('0x3f5CE5FBFe3E9af3971dD833D26bA9b5C936f0bE', force=True)

    # our actors:
    # whale is attacker
    # strategist is vault owner
    # honest_lp is a normal lp

    # ---- setup attacker ----
    balanceBefore = crEth.balanceOf(whale)* crEth.exchangeRateStored() /1e18

    #enter market that allows the whale to sell
    comptroller.enterMarkets([crSushi,crEth], {'from': whale} )

    #whale mints 1000 eth in cream
    crEth.mint({'from': whale, 'value': '1000 ether'})
    balanceAfter = crEth.balanceOf(whale)* crEth.exchangeRateStored() /1e18
    print('lent eth of whale ', (balanceAfter- balanceBefore)/1e18)
    print('liquid', comptroller.getAccountLiquidity(whale))


   # ------ setup vault ------ 
    vault = strategist.deploy(
        Vault, sushi, strategist, strategist, "TestVault", "Amount"
    )
    deposit_limit = Wei('100000000000000 ether')
    #set limit to the vault
    vault.setDepositLimit(deposit_limit, {"from": strategist})
    #deploy strategy
    strategy = strategist.deploy(TestHighYieldStrategy, vault)
    vault.addStrategy(strategy, deposit_limit, deposit_limit, 50, {"from": strategist})
    lps_funds = Wei('300000 ether')
    sushi.approve(vault,lps_funds, {"from": honest_lp})
    vault.deposit(lps_funds, {"from": honest_lp})
    strategy.harvest({'from': strategist})

    #now for the attack

    #whale sees harvest enter tx pool
    # this all happens in smart contract 
    # whale borrows 300k sushi
    attack_amount = 300000*1e18
    crSushi.borrow(attack_amount, {'from': whale})
    print('balance of whale ', sushi.balanceOf(whale)/1e18)
    #whale deposits
    sushi.approve(vault,attack_amount, {"from": whale})
    vault.deposit(attack_amount, {"from": whale})

    #harvest happens
    strategy.harvest({'from': strategist})

    #whale withdraws. Pays back loan. and keeps or sells profit
    vault.withdraw(vault.balanceOf(whale), {"from": whale})
    print('balance of whale ', sushi.balanceOf(whale)/1e18)
    sushi.approve(crSushi,crSushi.borrowBalanceStored(whale), {"from": whale})
    crSushi.repayBorrow(crSushi.borrowBalanceStored(whale),  {"from": whale})

    profit = sushi.balanceOf(whale)
    print('whale profit from attack = ', profit/1e18)
    print('whale profit share = ', (attack_amount+profit)/attack_amount)
    print("honest_lp share = ", vault.pricePerShare() /1e18)






