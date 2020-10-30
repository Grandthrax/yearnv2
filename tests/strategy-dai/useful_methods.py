from itertools import count
from brownie import Wei, reverts, network
import brownie
import requests


def get_gas_price(confirmation_speed: str = "fast"):
    if "mainnet" not in network.show_active():
        return 10 ** 9  # 1 gwei
    data = requests.get("https://www.gasnow.org/api/v3/gas/price").json()
    return data["data"][confirmation_speed]


def initialMigrate(strategy, vault, whale, ychad, dai, controller):
    print("\n----migrating strategy----")
    controller.approveStrategy(dai, strategy, {"from": ychad})
    controller.setStrategy(dai, strategy, {"from": ychad})
    vault.setMin(10000, {"from": ychad})
    assert controller.strategies(dai) == strategy
    daiInVault = dai.balanceOf(vault)
    earn(strategy, vault, ychad)
    deposit("10000 ether", whale, dai, vault)
    earn(strategy, vault, ychad)

    assert (dai.balanceOf(vault) == 0, "All money should now be in strat")
    assert (dai.balanceOf(strategy) == 0, "All money in strat should be invested")

    deposits, borrows = strategy.getCurrentPosition()
    assert (borrows > 0, "Should have borrowed some")
    assert (deposits > 0, "Should have lent some")


def harvest(strategy, keeper, vault):
    # Evaluate gas cost of calling harvest
    # gasprice = get_gas_price()
    gasprice = 30 * 1e9
    # txgas = strategy.harvest.estimate_gas()
    txgas = 1500000  # 1.5m
    txGasCost = txgas * gasprice
    avCredit = vault.creditAvailable(strategy)
    if avCredit > 0:
        print("Available credit from vault: ", avCredit / 1e18)
    harvestCondition = strategy.harvestTrigger(txGasCost, {"from": keeper})
    if harvestCondition:
        print("\n----bot calls harvest----")
        print("Tx harvest() gas cost: ", txGasCost / 1e18)
        print("Gas price: ", gasprice / 1e9)
        strategy.harvest({"from": keeper})


def tend(strategy, keeper):

    tendCondition = strategy.tendTrigger(0, {"from": keeper})

    if tendCondition:
        print("\n----bot calls tend----")
        strategy.tend({"from": keeper})


def stateOfStrat(strategy, dai, comp):
    print("\n----state of strat----")

    deposits, borrows = strategy.getCurrentPosition()
    compBal = comp.balanceOf(strategy)
    print("Comp:", Wei(compBal).to("ether"))
    print("DAI:", dai.balanceOf(strategy).to("ether"))
    print("borrows:", Wei(borrows).to("ether"))
    print("deposits:", Wei(deposits).to("ether"))
    realbalance = dai.balanceOf(strategy) + deposits - borrows
    print("total assets real:", realbalance.to("ether"))

    print("total assets estimate:", strategy.estimatedTotalAssets().to("ether"))
    if deposits == 0:
        collat = 0
    else:
        collat = borrows / deposits
    leverage = 1 / (1 - collat)
    print(f"calculated collat: {collat:.5%}")
    storedCollat = strategy.storedCollateralisation().to("ether")
    print(f"stored collat: {storedCollat:.5%}")
    print(f"leverage: {leverage:.5f}x")
    assert collat <= 0.75
    print("Expected Profit:", strategy.expectedReturn().to("ether"))


def assertCollateralRatio(strategy):
    deposits, borrows = strategy.getCurrentPosition()
    collat = borrows / deposits
    assert collat < strategy.collateralTarget() / 1e18


def stateOfVault(vault, strategy):
    print("\n----state of vault----")
    strState = vault.strategies(strategy)
    totalDebt = strState[5].to("ether")
    totalReturns = strState[6].to("ether")
    print(f"Total Strategy Debt: {totalDebt:.5f}")
    print(f"Total Strategy Returns: {totalReturns:.5f}")
    balance = vault.totalAssets().to("ether")
    print(f"Total Assets: {balance:.5f}")


def wait(time, chain):
    print(f"\nWaiting {time} blocks")
    chain.mine(time)


def deposit(amount, user, dai, vault):
    print("\n----user deposits----")
    dai.approve(vault, amount, {"from": user})
    print("deposit amount:", amount.to("ether"))
    vault.deposit(amount, {"from": user})


def withdraw(share, whale, dai, vault):

    print(f"\n----20 blocks later another user withdraws----")
    balanceBefore = dai.balanceOf(whale)
    balance = vault.balanceOf(whale)

    withdraw = min(balance, balance / share)
    vault.withdraw(withdraw, {"from": whale})
    balanceAfter = dai.balanceOf(whale)
    moneyOut = balanceAfter - balanceBefore


# print('Money Out:', Wei(moneyOut).to('ether'))
